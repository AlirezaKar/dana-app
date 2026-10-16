"""Regression tests for the explicitly requested folder watermark action."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from app_main.models import CaseSubmission
from .models import CaseImage
from .services.watermark import run_manual_for_folder


class ManualWatermarkTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_override = override_settings(STORAGE_ROOT=self.root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.rel = 'files/1405-07-24/123-alice'
        self.folder = self.root / self.rel
        self.folder.mkdir(parents=True)
        self.path = self.folder / 'car_card_front.jpg'
        Image.new('RGB', (600, 400), 'white').save(self.path)
        self.sub = CaseSubmission.objects.create(
            auth_username='alice', entered_file_code='123', insurance_type='body')
        self.image = CaseImage.objects.create(
            submission=self.sub, image_path=f'{self.rel}/{self.path.name}',
            original_name='photo.jpg', section='car_card_front',
            watermarked_at=timezone.now())
        session = self.client.session
        session['auth'] = {'username': 'alice'}
        session.save()
        self.url = reverse('storage_watermark', args=[self.rel])
        self.folder_url = reverse('storage_folder', args=[self.rel])

    @patch('app_media.services.watermark.simple_watermark_file')
    def test_get_never_stamps_and_folder_has_manual_button(self, stamp):
        response = self.client.get(self.folder_url)
        self.assertContains(response, 'manual watermark stamp')
        self.assertEqual(self.client.get(self.url).status_code, 405)
        stamp.assert_not_called()

    @patch('app_media.services.watermark.simple_watermark_file')
    def test_confirmation_required(self, stamp):
        self.assertRedirects(self.client.post(self.url), self.folder_url)
        stamp.assert_not_called()

    def test_manual_action_overwrites_and_updates_already_stamped_row(self):
        before = self.path.read_bytes()
        response = self.client.post(self.url, {'confirm': 'stamp'}, follow=True)
        self.assertRedirects(response, self.folder_url)
        self.assertNotEqual(self.path.read_bytes(), before)
        self.image.refresh_from_db()
        self.assertEqual(self.image.size_bytes, self.path.stat().st_size)
        self.assertIsNotNone(self.image.watermarked_at)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [self.path.name])
        self.assertContains(response, '۱ تصویر ذخیره شد')

    @patch('app_media.services.watermark.simple_watermark_file')
    def test_recursive_scope_metadata_and_non_image_skips(self, stamp):
        nested = self.folder / 'victim'
        nested.mkdir()
        bare = nested / 'photo.png'
        Image.new('RGB', (50, 50)).save(bare)
        (nested / 'note.txt').write_text('untouched')
        (nested / 'photo.heic').write_bytes(b'original HEIC')
        sibling = self.folder.parent / '456-alice'
        sibling.mkdir()
        Image.new('RGB', (50, 50)).save(sibling / 'outside.jpg')
        response = self.client.post(self.url, {'confirm': 'stamp'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(stamp.call_count, 2)
        calls = {call.args[0]: call.args[1] for call in stamp.call_args_list}
        self.assertEqual(set(calls), {self.path, bare})
        self.assertEqual(calls[self.path]['code'], '123')
        self.assertEqual(calls[self.path]['username'], 'alice')
        self.assertTrue(calls[bare]['at'])
        self.assertEqual((nested / 'photo.heic').read_bytes(), b'original HEIC')

    @patch('app_media.services.watermark.simple_watermark_file')
    def test_other_owner_and_shared_ancestor_rejected(self, stamp):
        other = self.folder.parent / '456-bob'
        other.mkdir()
        for subpath in ('files', 'files/1405-07-24', 'files/1405-07-24/456-bob', '../'):
            response = self.client.post(reverse('storage_watermark', args=[subpath]),
                                        {'confirm': 'stamp'})
            self.assertEqual(response.status_code, 404, subpath)
        stamp.assert_not_called()

    @patch('app_media.services.watermark.simple_watermark_file')
    def test_anonymous_and_csrf_protected(self, stamp):
        self.assertEqual(Client().post(self.url, {'confirm': 'stamp'}).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        self.assertEqual(client.post(self.url, {'confirm': 'stamp'}).status_code, 403)
        stamp.assert_not_called()

    @patch('app_media.services.watermark.simple_watermark_file')
    def test_staff_can_stamp_shared_folder(self, stamp):
        staff = get_user_model().objects.create_user('staff', is_staff=True)
        client = Client()
        client.force_login(staff)
        response = client.post(reverse('storage_watermark', args=['files']), {'confirm': 'stamp'})
        self.assertEqual(response.status_code, 302)
        stamp.assert_called_once()

    @patch('app_media.services.watermark.simple_watermark_file')
    def test_symlink_cannot_escape_selected_folder(self, stamp):
        external = self.root / 'outside.jpg'
        Image.new('RGB', (50, 50)).save(external)
        (self.folder / 'escape.jpg').symlink_to(external)
        self.client.post(self.url, {'confirm': 'stamp'})
        stamp.assert_called_once()
        self.assertEqual(stamp.call_args.args[0], self.path)

    @patch('app_media.services.watermark.simple_watermark_file', side_effect=OSError('bad image'))
    def test_failure_report_does_not_mark_success(self, stamp):
        old_timestamp = self.image.watermarked_at
        before = self.path.read_bytes()
        with self.assertLogs('app_media.services.watermark', level='ERROR'):
            result = run_manual_for_folder(self.folder, authorize=lambda path: None)
        self.assertEqual(result, {'done': 0, 'skipped': 0, 'failed': 1})
        self.image.refresh_from_db()
        self.assertEqual(self.image.watermarked_at, old_timestamp)
        self.assertEqual(self.path.read_bytes(), before)
