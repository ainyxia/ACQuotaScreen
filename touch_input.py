"""Single-pointer gestures decoded from the case panel's five-contact HID report."""


def contacts(report):
    if len(report) < 31 or report[0] != 1:
        return None
    result = {}
    for offset in range(1, 31, 6):
        flags, contact_id = report[offset:offset+2]
        x = int.from_bytes(bytes(report[offset+2:offset+4]), 'little')
        y = int.from_bytes(bytes(report[offset+4:offset+6]), 'little')
        if flags & 1 and 0 <= x <= 4096 and 0 <= y <= 4096:
            result[contact_id] = (x, y)
    return result


def position(point, rotation, width, height):
    x, y = (v/4096 for v in point)
    x, y = {270: (y, 1-x), 90: (1-y, x), 0: (x, y), 180: (1-x, 1-y)}[rotation]
    return round(x*(width-1)), round(y*(height-1))


class TouchTracker:
    def __init__(self):
        self.contact_id = None
        self.point = None

    def feed(self, report):
        current = contacts(report)
        if current is None:
            return []
        if self.contact_id is not None:
            if self.contact_id not in current:
                point = self.point
                self.contact_id = None
                self.point = None
                # A release report often has zero coordinates. Use the last valid point.
                return [('up', point)]
            point = current[self.contact_id]
            if point != self.point:
                self.point = point
                return [('move', point)]
            return []
        if current:
            self.contact_id = next(iter(current))
            self.point = current[self.contact_id]
            return [('down', self.point)]
        return []


def coalesce(events):
    result = []
    for event in events:
        if event[0] == 'move' and result and result[-1][0] == 'move':
            result[-1] = event
        else:
            result.append(event)
    return result
