"""Iranian plate helpers — one plate, two halves (v1.21).

A plate is stored the way the insurance tables store it: the main part
(``94س225``) and the «ایران ##» serial (``63``) **separately**. These two
functions convert between that pair and the eight boxes of the plate widget
(``templates/main/_plate.html``) — the only place in the app that knows the
layout of the component.
"""
from app_core.utils.digits import to_en

#: the box names of the widget, in DOM order
SLOT_KEYS = ('plate_d1', 'plate_d2', 'plate_letter', 'plate_d3',
             'plate_d4', 'plate_d5', 'plate_ir1', 'plate_ir2')


def plate_slots(plate_value, plate_serial=''):
    """``{'plate_d1': …, 'plate_ir2': …}`` — the widget's boxes, filled in.

    Accepts the combined form too (``94س225-63``), so a value typed anywhere in
    the app can be shown back the way it was entered.
    """
    slots = {key: '' for key in SLOT_KEYS}
    main, _, tail = str(plate_value or '').partition('-')
    if len(main) >= 6:
        slots['plate_d1'], slots['plate_d2'] = main[0], main[1]
        slots['plate_letter'] = main[2]
        slots['plate_d3'], slots['plate_d4'], slots['plate_d5'] = main[3], main[4], main[5]
    elif main:                                   # a short/odd value: show the digits
        for i, ch in enumerate(main[:5]):
            slots[f'plate_d{i + 1}'] = ch
    serial = to_en((plate_serial or tail or '')).replace('-', '').strip()
    if len(serial) >= 2:
        slots['plate_ir1'], slots['plate_ir2'] = serial[0], serial[1]
    return slots


def build_plate_value(p):
    """Assemble posted form fields into ``(plate, serial)`` — Excel format.

    ``p`` is the POST dict; the field names are the ones
    ``templates/main/_plate.html`` renders (with whatever prefix it was given
    stripped by the caller).
    """
    def d(name):
        return to_en(p.get(name, '') or '').strip()

    letter = (p.get('plate_letter', '') or '').strip()
    d1, d2 = d('plate_d1'), d('plate_d2')
    d3, d4, d5 = d('plate_d3'), d('plate_d4'), d('plate_d5')
    ir1, ir2 = d('plate_ir1'), d('plate_ir2')
    plate = f'{d1}{d2}{letter}{d3}{d4}{d5}' if (d1 and d2 and letter and d3 and d4 and d5) else ''
    serial = f'{ir1}{ir2}' if (ir1 and ir2) else ''
    return plate, serial
