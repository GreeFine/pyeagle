import math

from lxml.etree import tostring
from lxml.builder import E

# PCB layers
PADS_LAYER = 17
VIAS_LAYER = 18
HOLES_LAYER = 45
DRILLS_LAYER = 44

TOP_LAYER = 1
BOTTOM_LAYER = 16

# Schematic layers
SYMBOLS_LAYER = 94
PINS_LAYER = 93


class Primitive(object):

    def to_svg_bounding_box(self, scale, margin):
        (startx, starty), (endx, endy) = self.bounding_box()
        width = math.ceil((endx - startx) * scale)
        height = math.ceil((endy - starty) * scale)

        style = 'stroke-width:1; stroke:red; fill:rgba(255, 0, 0, 0.1);'
        return E.rect(
            x=str(margin),
            y=str(margin),
            width=str(width),
            height=str(height),
            style=style,
        )

    def to_svg(self, scale, layers, margin=10, add_bounding_box=False):
        """
        Render this piece of geometry or set of pieces to an SVG object, and
        return it as a string.
        """
        (startx, starty), (endx, endy) = self.bounding_box()

        width = math.ceil((endx - startx) * scale)
        height = math.ceil((endy - starty) * scale)

        offset_margin = float(margin) / scale

        offset = (-startx + offset_margin, -starty + offset_margin)

        children = self.to_svg_fragments(offset, scale, layers)

        if add_bounding_box:
            children.insert(0, self.to_svg_bounding_box(scale, margin))

        root = E.svg(
            *children,
            width=str(width + (2 * margin)),
            height=str(height + (2 * margin)))
        return tostring(root)


class Wire(Primitive):
    def __init__(self, start, end, width, layer, curve=None, cap=None):
        self.x1, self.y1 = start
        self.x2, self.y2 = end
        self.width = width
        self.layer = layer
        self.curve = curve
        self.cap = cap

    def __repr__(self):
        return '<%s (%f, %f) -> (%f, %f)>' % (self.__class__.__name__,
                                              self.x1, self.y1,
                                              self.x2, self.y2)

    @classmethod
    def from_xml(cls, node):
        """
        Construct a Wire from an EAGLE XML ``wire`` node.
        """
        curve = node.attrib.get('curve')
        curve = curve and float(curve)
        return cls(start=(float(node.attrib['x1']),
                          float(node.attrib['y1'])),
                   end=(float(node.attrib['x2']),
                        float(node.attrib['y2'])),
                   width=float(node.attrib['width']),
                   layer=int(node.attrib['layer']),
                   curve=curve,
                   cap=node.attrib.get('cap'))

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        return ((min(self.x1, self.x2), min(self.y1, self.y2)),
                (max(self.x1, self.x2), max(self.y1, self.y2)))

    def to_svg_fragments(self, offset, scale, layers):
        offx, offy = offset

        color = layers.get_css_color(self.layer)
        if color:
            style = 'stroke:%s;stroke-width:%d' % (color, self.width * scale)

            return [E.line(
                x1=str((self.x1 + offx) * scale),
                y1=str((self.y1 + offy) * scale),
                x2=str((self.x2 + offx) * scale),
                y2=str((self.y2 + offy) * scale),
                style=style,
            )]
        else:
            return []


class SMD(Primitive):
    def __init__(self, name, pos, size, layer):
        self.name = name
        self.x, self.y = pos
        self.dx, self.dy = size
        self.layer = layer

    def __repr__(self):
        return '<%s %r (%f, %f)>' % (self.__class__.__name__,
                                     self.name,
                                     self.x, self.y)

    @classmethod
    def from_xml(cls, node):
        """
        Construct an SMD from an EAGLE XML ``smd`` node.
        """
        return cls(name=node.attrib['name'],
                   pos=(float(node.attrib['x']),
                        float(node.attrib['y'])),
                   size=(float(node.attrib['dx']),
                         float(node.attrib['dy'])),
                   layer=int(node.attrib['layer']))

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        return ((self.x - (self.dx / 2.0), self.y - (self.dy / 2.0)),
                (self.x + (self.dx / 2.0), self.y + (self.dy / 2.0)))

    def to_svg_fragments(self, offset, scale, layers):
        offsetx, offsety = offset

        color = layers.get_css_color(self.layer)
        if color:
            style = 'fill:%s' % color

            return [E.rect(
                x=str((self.x + offsetx - (self.dx / 2.0)) * scale),
                y=str((self.y + offsety - (self.dy / 2.0)) * scale),
                width=str(self.dx * scale),
                height=str(self.dy * scale),
                style=style,
            )]
        else:
            return []


class Text(Primitive):
    def __init__(self, s, pos, size, layer, ratio=None):
        self.s = s
        self.x, self.y = pos
        # This is the height of the text.
        self.size = size
        self.layer = layer
        # This is the 'boldness' of the text.
        self.ratio = ratio

    def __repr__(self):
        return '<%s %r (%f, %f)>' % (self.__class__.__name__,
                                     self.s,
                                     self.x, self.y)

    @classmethod
    def from_xml(cls, node):
        """
        Construct a Text instance from an EAGLE XML ``<text>`` node.
        """
        ratio = node.attrib.get('ratio')
        ratio = ratio and float(ratio)
        return cls(s=node.text,
                   pos=(float(node.attrib['x']),
                        float(node.attrib['y'])),
                   size=float(node.attrib['size']),
                   layer=int(node.attrib['layer']),
                   ratio=ratio)

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        # FIXME Can we actually calculate this? May need to render text.
        w, h = self.calculate_size(scale=1)
        baseline = 0.25  # Consolas
        offset = baseline * self.size
        return ((self.x, self.y - h + offset),
                (self.x + w, self.y + offset))

    def calculate_size(self, scale):
        aspect_ratio = 0.55  # Consolas
        h = self.size * scale
        w = h * aspect_ratio * len(self.s)
        return w, h

    def to_svg_fragments(self, offset, scale, layers):
        offsetx, offsety = offset

        color = layers.get_css_color(self.layer)
        if color:
            # Initial super naive approach assumes one size and no ratio
            style = ('fill:%s; font-size:%f; font-family:Consolas;' %
                     (color, self.size * scale))

            return [
                E.text(
                    self.s,
                    x=str((self.x + offsetx) * scale),
                    y=str((self.y + offsety) * scale),
                    style=style,
                )
            ]
        else:
            return []


class Rectangle(Primitive):
    def __init__(self, start, end, layer):
        self.x1, self.y1 = start
        self.x2, self.y2 = end
        self.layer = layer

    def __repr__(self):
        return '<%s (%f, %f) -> (%f, %f)>' % (self.__class__.__name__,
                                              self.x1, self.y1,
                                              self.x2, self.y2)

    @classmethod
    def from_xml(cls, node):
        """
        Construct a Rectangle from an EAGLE XML ``<rectangle>`` node.
        """
        return cls(start=(float(node.attrib['x1']),
                          float(node.attrib['y1'])),
                   end=(float(node.attrib['x2']),
                        float(node.attrib['y2'])),
                   layer=int(node.attrib['layer']))

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        return ((min(self.x1, self.x2), min(self.y1, self.y2)),
                (max(self.x1, self.x2), max(self.y1, self.y2)))

    def to_svg_fragments(self, offset, scale, layers):
        offsetx, offsety = offset

        color = layers.get_css_color(self.layer)
        if color:
            style = 'fill:%s' % color

            x = min(self.x1, self.x2)
            y = min(self.y1, self.y2)
            width = abs(self.x2 - self.x1)
            height = abs(self.y2 - self.y1)

            return [E.rect(
                x=str((x + offsetx) * scale),
                y=str((y + offsety) * scale),
                width=str(width * scale),
                height=str(height * scale),
                style=style,
            )]

        else:
            return []


class Pad(Primitive):
    def __init__(self, name, pos, drill, diameter):
        self.name = name
        self.x, self.y = pos
        self.drill = drill
        self.diameter = diameter

    def __repr__(self):
        return '<%s (%f, %f) %f>' % (self.__class__.__name__,
                                     self.x, self.y,
                                     self.diameter)

    @classmethod
    def from_xml(cls, node):
        return cls(name=node.attrib['name'],
                   pos=(float(node.attrib['x']),
                        float(node.attrib['y'])),
                   drill=float(node.attrib['drill']),
                   diameter=float(node.attrib.get('diameter', 0)))

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        margin = self.diameter / 2.0
        return ((self.x - margin,
                 self.y - margin),
                (self.x + margin,
                 self.y + margin))

    def to_svg_fragments(self, offset, scale, layers):
        # FIXME Implement this

        # Initial naive approach is to ignore the pad shape and just assume
        # it's circular.
        offsetx, offsety = offset

        color = layers.get_css_color(PADS_LAYER)
        if color:
            style = 'fill:%s;stroke-width:%d' % (color, 0)

            return [E.circle(
                r=str((self.diameter / 2.0) * scale),
                cx=str((self.x + offsetx) * scale),
                cy=str((self.y + offsety) * scale),
                style=style,
            )]
        else:
            return []

        return []


class Pin(Primitive):
    pin_origin_radius = 0.508

    def __init__(self, name, pos, length, direction, function, rotate,
                 visible=False):
        self.name = name
        self.x, self.y = pos
        self.visible = visible

        # The length of the pin:
        #   - point: pin has no length
        #   - short: pin is 0.1" long
        #   - middle: pin is 0.2" long
        #   - logn: pin is 0.3" long

        self.length = length

        # The 'direction' of the pin. Doesn't affect rendering, just electrical
        # rule check. Possible values are:
        #   - nc
        #   - in
        #   - out
        #   - io
        #   - oc
        #   - pwr
        #   - pas
        #   - hiz
        #   - sup
        self.direction = direction

        # The 'function' of the pin. Can be none (missing), dot, clk, or dotclk
        self.function = function

        # With no rotation (0) the pin is horizontal, with the origin on the
        # left side. With 90 degrees of rotation, the pin is vertical, with the
        # origin on the bottom.
        self.rotate = rotate

    def __repr__(self):
        return ('<%s %r (%s, %s) %f, %f R%d>' %
                (self.__class__.__name__,
                 self.name,
                 self.direction,
                 self.function,
                 self.x,
                 self.y,
                 self.rotate))

    @classmethod
    def from_xml(cls, node):
        visible = node.attrib.get('visible') != 'off'
        rotate = int(node.attrib.get('rot', 'R0')[1:])
        return cls(name=node.attrib['name'],
                   pos=(float(node.attrib['x']),
                        float(node.attrib['y'])),
                   length=node.attrib['length'],
                   direction=node.attrib.get('direction'),
                   function=node.attrib.get('function'),
                   rotate=rotate,
                   visible=visible)

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        endx, endy = self.calculate_line_endpoint()
        if self.rotate == 0:
            startx = self.x - self.pin_origin_radius
            starty = self.y - self.pin_origin_radius
            endy += self.pin_origin_radius
            return (startx, starty), (endx, endy)
        elif self.rotate == 90:
            startx = self.x - self.pin_origin_radius
            starty = self.y - self.pin_origin_radius
            endx += self.x - self.pin_origin_radius
            return (startx, starty), (endx, endy)
        elif self.rotate == 180:
            startx = self.x + self.pin_origin_radius
            starty = self.y + self.pin_origin_radius
            endy -= self.pin_origin_radius
            return (endx, endy), (startx, starty)
        elif self.rotate == 270:
            startx = self.x + self.pin_origin_radius
            starty = self.y + self.pin_origin_radius
            endx -= self.pin_origin_radius
            return (endx, endy), (startx, starty)

    def calculate_line_endpoint(self):
        grid_scale = 2.54
        length = {'point': 0,
                  'short': 1,
                  'middle': 2,
                  'long': 3}[self.length] * grid_scale
        if self.rotate == 0:
            end = self.x + length, self.y
        elif self.rotate == 90:
            end = self.x, self.y + length
        elif self.rotate == 180:
            end = self.x - length, self.y
        elif self.rotate == 270:
            end = self.x, self.y - length
        return end

    def to_svg_fragments(self, offset, scale, layers):
        offx, offy = offset
        elements = []
        # FIXME Implement this

        # Pin rendering consists of a couple things:
        #   - the pin itself
        #   - the function of the pin
        #   - text annotations
        #   - the label text?

        # Components:
        #   - pin line
        endx, endy = self.calculate_line_endpoint()
        color = layers.get_css_color(SYMBOLS_LAYER)
        if color:
            style = 'stroke:%s;stroke-width:%d' % (color, 1)

            elements.append(E.line(
                x1=str((self.x + offx) * scale),
                y1=str((self.y + offy) * scale),
                x2=str((endx + offx) * scale),
                y2=str((endy + offy) * scale),
                style=style,
            ))

        #   - pin origin circle
        color = layers.get_css_color(PINS_LAYER)
        if color:
            style = 'stroke:%s;stroke-width:%d;fill:transparent;' % (color, 1)
            elements.append(E.circle(
                r=str(self.pin_origin_radius * scale),
                cx=str((self.x + offx) * scale),
                cy=str((self.y + offy) * scale),
                style=style,
            ))
        #   - dot function (optional)
        #   - clk function (optional)
        #   - name label
        #   - direction label

        return elements


class Polygon(Primitive):
    def __init__(self, width, layer, vertices=None):
        self.width = width
        self.layer = layer
        self.vertices = vertices or []

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__,
                            self.vertices)

    @classmethod
    def from_xml(cls, node):
        vertices = []
        for vertex_node in node.xpath('vertex'):
            vertices.append((float(vertex_node.attrib['x']),
                             float(vertex_node.attrib['y'])))
        return cls(width=float(node.attrib['width']),
                   layer=int(node.attrib['layer']),
                   vertices=vertices)

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        margin = self.width / 2.0
        return ((min(x for x, y in self.vertices) - margin,
                 min(y for x, y in self.vertices) - margin),
                (max(x for x, y in self.vertices) + margin,
                 max(y for x, y in self.vertices) + margin))

    def to_svg_fragments(self, offset, scale, layers):
        offsetx, offsety = offset

        color = layers.get_css_color(self.layer)
        if color:
            # FIXME Handle stroke and fill correctly.
            style = 'fill:%s;stroke:%s;stroke-width:%d' % (color, color,
                                                           self.width * scale)
            points = ' '.join('%d,%d' % ((x + offsetx) * scale,
                                         (y + offsety) * scale)
                              for x, y in self.vertices)
            return [E.polygon(points=points, style=style)]
        else:
            return []


class Hole(Primitive):
    def __init__(self, pos, drill):
        self.x, self.y = pos
        self.drill = drill

    def __repr__(self):
        return '<%s (%f, %f)>' % (self.__class__.__name__,
                                  self.x, self.y)

    @classmethod
    def from_xml(cls, node):
        return cls(pos=(float(node.attrib['x']),
                        float(node.attrib['y'])),
                   drill=float(node.attrib['drill']))

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        margin = self.drill / 2.0
        return ((self.x - margin,
                 self.y - margin),
                (self.x + margin,
                 self.y + margin))

    def to_svg_fragments(self, offset, scale, layers):
        offsetx, offsety = offset

        color = layers.get_css_color(HOLES_LAYER)
        if color:
            style = ('fill:rgba(0, 0, 0, 0);stroke:%s;stroke-width:%d' %
                     (color, 1))

            return [E.circle(
                r=str((self.drill / 2.0) * scale),
                cx=str((self.x + offsetx) * scale),
                cy=str((self.y + offsety) * scale),
                style=style,
            )]
        else:
            return []


class Circle(Primitive):
    def __init__(self, pos, radius, width, layer):
        self.x, self.y = pos
        self.radius = radius
        self.width = width
        self.layer = layer

    def __repr__(self):
        return '<%s (%f, %f) %f>' % (self.__class__.__name__,
                                     self.x, self.y,
                                     self.radius)

    @classmethod
    def from_xml(cls, node):
        return cls(pos=(float(node.attrib['x']),
                        float(node.attrib['y'])),
                   radius=float(node.attrib['radius']),
                   width=float(node.attrib['width']),
                   layer=int(node.attrib['layer']))

    def to_xml(self):
        """
        Serialize this primitive element to a fragment in EAGLE's XML format.
        """
        raise NotImplementedError

    def bounding_box(self):
        margin = self.radius + (self.width / 2.0)
        return ((self.x - margin, self.y - margin),
                (self.x + margin, self.y + margin))

    def to_svg_fragments(self, offset, scale, layers):
        offsetx, offsety = offset

        color = layers.get_css_color(self.layer)
        if color:
            style = ('fill:rgba(0, 0, 0, 0);stroke:%s;stroke-width:%d' %
                     (color, 1))

            return [E.circle(
                r=str(self.radius * scale),
                cx=str((self.x + offsetx) * scale),
                cy=str((self.y + offsety) * scale),
                style=style,
            )]
        else:
            return []


class Geometry(Primitive):
    def __init__(self, primitives=None):
        self.primitives = primitives or []

    @staticmethod
    def geometry_from_xml(node):
        primitives = []
        for cls, tag in [(Wire, 'wire'),
                         (SMD, 'smd'),
                         (Text, 'text'),
                         (Rectangle, 'rectangle'),
                         (Polygon, 'polygon'),
                         (Hole, 'hole'),
                         (Pad, 'pad'),
                         (Pin, 'pin')]:
            for subnode in node.xpath(tag):
                primitives.append(cls.from_xml(subnode))
        return primitives

    def bounding_box(self):
        startx = starty = endx = endy = 0
        for primitive in self.primitives:
            (x1, y1), (x2, y2) = primitive.bounding_box()
            startx = min(startx, x1)
            starty = min(starty, y1)
            endx = max(endx, x2)
            endy = max(endy, y2)
        return (startx, starty), (endx, endy)

    def to_svg_fragments(self, offset, scale, layers):
        """
        Render this set of geometry to a list of SVG nodes.

        :param scale:
            Scaling factor
        :type scale:
            int
        """
        children = []
        for primitive in self.primitives:
            children.extend(primitive.to_svg_fragments(offset, scale, layers))
        return children
