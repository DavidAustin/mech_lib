# TODO -
# * search for data by component name too - generally refactor data search?
# * each part able to run openscad to generate itself (scad, stl, csg)
#   (in a sub-dir)
# * BOM generation (spreadsheeet, csv?)
# * interfacing between parts - able to specify mating constraints/locations
#   and assemble by those.

import sys
import os
import math
from solid import *
from solid.utils import *
from solid import screw_thread
import pickle

aluminium_colour = [0.77, 0.77, 0.8]
steel_colour = [0.7, 0.7, 0.7]#[0.8, 0.8, 0.8]


TransparentYellow = (1, 1, 0, 0.3)


def make_routed_slot(pts, tool_dia):
    import shapely
    import shapely.geometry
    l = shapely.geometry.LineString(pts)
    p = l.buffer(distance=tool_dia/2, resolution=2)#, cap_style=1, join_style=1)
    pts = [(e[0],e[1]) for e in p.exterior.coords]
    return pts

class AssemblyBase(object):

    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.parent = None
        self.children = []
        self.calculated = False
        self.calculating = False
        self.identifier = name
        self.id_dict = {}

    def add_child(self, child):
        self.children.append(child)        
        child.set_parent(self)
        if self.calculating:
            child.calculate()
                            

    def add_children(self, *args):
        for a in args:
            if isinstance(a, (list,tuple)):
                self.add_children(*a)
            else:
                self.add_child(a)       

    def set_parent(self, parent):
        self.parent = parent

    def get_top(self):
        if self.parent is None:
            return self
        else:
            return self.parent.get_top()

    def get_data(self, key, default=None):
        data_depth = self.get_data_depth(key)
        if len(data_depth) > 0:            
            data_depth.sort(key=lambda e: e[1])
            return data_depth[0][0]
        
        ud = self.get_data_up(key)
        if ud is not None:
            return ud
        else:
            return default
       
    def get_data_depth(self, key, depth=0):
        #print key, depth, self.name
        if key in self.data:
            return [(self.data[key], depth)]
        else:
            ret = []
            for c in self.children:
                dd = c.get_data_depth(key, depth+1)
                if dd is not None:
                    ret += dd
            return ret

    def get_data_up(self, key):
        if key in self.data:
            return self.data[key]
        elif self.parent is None:
            return None
        else:
            return self.parent.get_data_up(key)

    def finalise_calcs(self, tries=5, exception_on_fail=True):
        while tries >= 0:
            if self.recalculate(show_errors=(tries==0)):
                return True
            tries -= 1
        if exception_on_fail:
            raise RuntimeError, "finalise_calcs failed"
        else:
            return False
    
    def recalculate(self, show_errors=False):
        done = True
        for c in self.children:
            r = c.recalculate(show_errors=show_errors)
            if not r:
                if show_errors:
                    print "Recalculate failed for %s" % c.name
                done = False
        r = self.check_calculate()
        if not r:
            if show_errors:
                print "Calculate failed for %s" % self.name
            done = False
        return done

    def check_calculate(self):
        if self.calculated:
            return True
        self.calculating = True
        r = self.calculate()
        self.calculating = False
        if r:
            self.calculated = r
        return r
    
    def calculate(self):
        return False
        
    def generate(self):
        raise NotImplementedError, "Should be overridden"

    def make_id(self):
        basename = self.identifier
        id_dict = self.get_top().id_dict
        t = basename
        d = id_dict.get(t, None)
        if d is self:
            return None
        elif d is None:
            id_dict[t] = self
            self.identifier = t
            print '%s:Allocating new id %s to %s' % (
                self.get_top().identifier, t, self
            )
        else:
            i = 0
            while True:
                t = basename + '_' + str(i)
                d = id_dict.get(t, None)
                if d is self or d is None:
                    break
                
                i += 1
            print '%s:Allocating new id %s to %s' % (
                self.get_top().identifier, t, self
            )
            id_dict[t] = self
            self.identifier = t
        
    def gen_unique_ids(self):
        self.make_id()
        for c in self.children:
            c.gen_unique_ids()
    
    def make_bom(self):
        self.get_top().gen_unique_ids()
        ret = []
        self.do_make_bom(ret)
        return ret

    def do_make_bom(self, l):
        l.append({'name': self.name,
                  'identifier' : self.identifier,
                  'data' : self.data,
                  'assembly' : len(self.children) > 0})
        for c in self.children:
            c.do_make_bom(l)


    def save_data(self, output_dir):
        self.get_top().gen_unique_ids()
        self.get_top().do_save(output_dir)

    def do_save(self, output_dir):
        ofn = os.path.join(output_dir, '%s.pickle' %  (self.identifier))
        pickle.dump(self.data, open(ofn, 'w'))
        for c in self.children:
            c.do_save(output_dir)
        
    def save_components(self, output_dir):
        self.get_top().gen_unique_ids()
        self.get_top().do_save_components(output_dir)

    def do_save_components(self, output_dir):
        ofn = os.path.join(output_dir, '%s.scad' %  (self.identifier))
        pickle.dump(self.data, open(ofn, 'w'))
        scad_render_to_file(self.generate(),
                            filepath=ofn,
                            include_orig_code=True,
                            file_header='$fa = %s; $fn = %s;' % (40, 40))
        for c in self.children:
            c.do_save_components(output_dir)
        
def print_bom(bom):
    for d in bom:
        if not d['assembly']:
            print d['identifier'], d['name'], d['data']
    print ''
    for d in bom:
        if d['assembly']:
            print d['identifier'], d['name'], d['data']
        
def mirror_points_x(pts, x_val):
    r = []
    for x,y in pts:
        x = 2 * x_val - x
        r.append((x,y))
    r.reverse()
    return r

def shift_points(pts, s):
    r = []
    for x,y in pts:
        x += s[0]
        y += s[1]
        r.append([x, y])
    return r

def rotate_points(pts, angle):
    ca = math.cos(angle)
    sa = math.sin(angle)
    r = []
    for x,y in pts:
        nx = x * ca - y * sa
        ny = x * sa + y * ca
        r.append([nx, ny])
    return r


class GenericRectangularPrism(AssemblyBase):
    def __init__(self, name, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, name, defaults)

    def calculate(self):
        return True

    def generate(self):
        colour = self.get_data('colour', Yellow)
        width = self.get_data('width')
        height = self.get_data('height')
        depth = self.get_data('depth')
        return color(colour)(cube([width, depth, height]))

class GenericDrilledPlate(AssemblyBase):
    def __init__(self, name, data={}):
        defaults = {            
        }
        defaults.update(data)
        AssemblyBase.__init__(self, name, defaults)

    def calculate(self):
        nd = []
        width = self.get_data('width')
        depth = self.get_data('depth')
        drills = self.get_data('drills', [])
        for x,y,dia in drills:
            if x < 0:
                x = width + x
            if y < 0:
                y = depth + y
            nd.append([x,y,dia])
        self.data['drills'] = nd
        return True

    def generate(self):
        colour = self.get_data('colour', Yellow)
        width = self.get_data('width')
        height = self.get_data('height')
        depth = self.get_data('depth')
        drills = self.get_data('drills', [])
        u = cube([width, depth, height])
        dl = []
        for x,y,dia in drills:
            dl.append(translate([x,y,-1])(cylinder(r=float(dia)/2,
                                                   h = height+2)))
        u = difference()(
            u,
            *dl
        )
        return color(colour)(u)



class GenericRHS(AssemblyBase):
    def __init__(self, name, data={}):
        defaults = {            
        }
        defaults.update(data)
        AssemblyBase.__init__(self, name, defaults)

    def calculate(self):
        return True

    def generate(self):
        colour = self.get_data('colour', Yellow)
        width = self.get_data('width')
        height = self.get_data('height')
        length = self.get_data('length')
        thickness = self.get_data('thickness')

        pts = [
            [0.0, 0.0],
            [width, 0.0],
            [width, thickness],
            [thickness, thickness],
            [thickness, height],
            [0.0, height],
            [0.0, 0.0]
        ]
        
        u = linear_extrude(length, convexity=2)(polygon(pts))
        
        return color(colour)(u)


def metric_bolt(d, l, style='socket_head'):
    r = float(d)/2.0
    if style == 'socket_head':
        head = cylinder(r=2*r, h=d)
        head = difference()(head, 
                            translate([0, 0, r])(cylinder(r=float(r),
                                                          h=r+1, segments=6)))
        remaining_len = l - d
    else:
        raise NotImplementedError, 'unknown head style %s' % style
    return color([0.1,0.1,0.1])(union()(
        head,
        translate([0,0,-remaining_len])(
            cylinder(r=r,
                     h=remaining_len)))
    )
    


def beam20x20(l):
    beam_corner = circle(r=1.5)
    beam_square = minkowski()(translate([1.5, 1.5, 0])(square(20.0 - 3)),
                              beam_corner)
    #beam_square = union()(square(20.0 - 3), beam_corner)
    tslot = [
        (0,   3.8),
        (0,   2.7),
        (2.4, 0),
        (8.6, 0),
        (11,  2.7),
        (11,  3.8),
        (8.6, 3.8),
        (8.6, 6.1),
        (2.4, 6.1),
        (2.4, 3.8),
        (0,   3.8),
    ]
        
    beam_shape = difference()(
        beam_square,
        translate([4.5,6.1,0])(rotate([180,0,0])(polygon(tslot))),
        translate([4.5,13.9,0])(rotate([0,0,0])(polygon(tslot))),
        translate([6.1,4.5,0])(rotate([0,0,90])(polygon(tslot))),
        translate([14,4.5,0])(rotate([180,0,90])(polygon(tslot)))
    )
                                           
    beam = linear_extrude(l)(beam_shape)
                                           
    return color(aluminium_colour)( 
        beam
    )




def beam40x20(l):
    beam_corner = circle(r=1.5)
    beam_square = minkowski()(translate([1.5, 1.5, 0])(square([20.0 - 3,
                                                               40.0 - 3])),
                              beam_corner)

    
    tslot = [
        (0,   3.8),
        (0,   2.7),
        (2.4, 0),
        (8.6, 0),
        (11,  2.7),
        (11,  3.8),
        (8.6, 3.8),
        (8.6, 6.1),
        (2.4, 6.1),
        (2.4, 3.8),
        (0,   3.8),
    ]

    hollow = [
        (-7.0, -2.0),
        (-8.0, -2.0),
        (-8.0, 2.0),
        (-7.0, 2.0),
        
        (-2.0, 7.0),
        (-2.0, 8.0),
        (2.0, 8.0),
        (2.0, 7.0),

        (7.0, 2.0),
        (8.0, 2.0),
        (8.0, -2.0),
        (7.0, -2.0),

        (2.0, -7.0),
        (2.0, -8.0),
        (-2.0, -8.0),
        (-2.0, -7.0),

        (-7.0, -2.0)
    ]
        
    beam_shape = difference()(
        beam_square,
        translate([10.0, 20.0, 0])(polygon(hollow)),
        translate([4.5,6.1,0])(rotate([180,0,0])(polygon(tslot))),

        translate([4.5,13.9+20.01,0])(rotate([0,0,0])(polygon(tslot))),

        translate([6.1,4.5,0])(rotate([0,0,90])(polygon(tslot))),
        translate([6.1,4.5+20,0])(rotate([0,0,90])(polygon(tslot))),

        translate([14,4.5,0])(rotate([180,0,90])(polygon(tslot))),
        translate([14,4.5+20.0,0])(rotate([180,0,90])(polygon(tslot)))
    )
                                           
    beam = linear_extrude(l)(beam_shape)
                                           
    return color(aluminium_colour)( 
        beam
    )


def beam40x40(l):
    pts = [
        [5.5, 4.1],
        [5.5, -4.1],
        [13.0, -10.25],
        [18.2, -10.25],
        [18.2, -6.4],
        [15.5, -6.4],
        [15.5, -4.1],
        [20.0, -4.1],
        [20.0, -20.0],
        [4.1, -20.0],
        [4.1, -15.5],
        [6.4, -15.5],
        [6.4, -18.2],
        [10.25, -18.2],
        [10.25, -13.0],
        [4.1, -5.5],
    ]

    all_pts = (pts + rotate_points(pts, math.radians(90))
               + rotate_points(pts, math.radians(180)) 
               + rotate_points(pts, math.radians(270)))
    beam = linear_extrude(l)(polygon(all_pts))
                                           
    return color(aluminium_colour)( 
        beam
    )

class Beam40x40(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, "Beam40x40", defaults)

    def calculate(self):
        return True

    def generate(self):
        return beam40x40(self.data['length'])


def mgn12_rail(l):

    h = 13.0 - 5.0
    c = 0.25
    p = [
        (-6.0, 0),
        (-6.0, 3.0),
        (-6.0, 4.5),
        (-5.0, 5.5),
        (-4.8, 5.5),
        (-4.8, 6.0),
        (-5.0, 6.0),
        (-6.0, 7.0),       
        (-6.0, h-c),
        (-6.0+c, h),

        (6.0-c, h),
        (6.0, h-c),
        (6.0, 7.0),       
        (5.0, 6.0),
        (4.8, 6.0),
        (4.8, 5.5),
        (5.0, 5.5),
        (6.0, 4.5),
        (6.0, 3.0),
        (6.0, 0.0),
        (-6.0, 0.0)
        ]
    beam = linear_extrude(l)(polygon(p))
    beam = rotate([90,0,90])(beam)
    return color(steel_colour)( 
        beam
    )



def mgn12h_slider():
    w = 27.0
    l = 45.4
    red_l = 1.0
    green_l = 4.0
    steel_l = l - 2*(red_l + green_l)
    s = union()(
        color(steel_colour)(
            translate([-steel_l/2, -w/2, 3])(cube([steel_l, w, 10]))
        ),
        color([0, 0.7, 0])(
            translate([steel_l/2, -w/2, 3])(cube([green_l, w, 10]))
        ),
        color([0.8, 0.0, 0])(
            translate([steel_l/2 + green_l, -w/2, 3])(cube([red_l, w, 10]))
        ),

        color([0, 0.7, 0])(
            translate([-steel_l/2 - green_l, -w/2, 3])(cube([green_l, w, 10]))
        ),
        color([0.8, 0.0, 0])(
            translate([-steel_l/2 - green_l - red_l, -w/2, 3])(
                cube([red_l, w, 10])
            )
        ),
        
    )

    
    beam = translate([-1-l/2, 0, 0])(mgn12_rail(l + 2))

    C = 20.0
    B = 20.0
    s = difference()(
        s,
        beam,
        translate([-C/2, -B/2, 10])(cylinder(r=2.6/2, h=20.0)),
        translate([-C/2,  B/2, 10])(cylinder(r=2.6/2, h=20.0)),
        translate([ C/2, -B/2, 10])(cylinder(r=2.6/2, h=20.0)),
        translate([ C/2,  B/2, 10])(cylinder(r=2.6/2, h=20.0)),
    )
    return s
    

def shaft(dia=10.0, length=300.0):
    return color(steel_colour)(cylinder(r=float(dia)/2, h=length))


class GenericShaft(AssemblyBase):
    def __init__(self, name, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, name, defaults)

    def calculate(self):
        return True

    def generate(self):
        colour = self.get_data('colour', Yellow)
        dia = self.get_data('dia')
        length = self.get_data('length')
        return color(colour)(cylinder(r=float(dia)/2, h=length))


class GenericBearing(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'Bearing', defaults)

    def calculate(self):
        return True

    def generate(self):
        ind = self.data['bearing_id']
        od = self.data['bearing_od']
        t = self.data['thickness']
        dr = float(od)/2/8
        u = union()(
            color(Steel)(
                difference()(
                    cylinder(r=float(od)/2,h=t),
                    translate([0,0,-1])(
                        cylinder(r=float(od)/2 - dr, h=t+2)
                    )
                ),
                difference()(
                    cylinder(r=float(ind)/2+dr, h=t),
                    translate([0,0,-1])(
                        cylinder(r=float(ind)/2, h=t+2)
                    )
                )
            ),
            color(Black)(
                difference()(
                    cylinder(r=float(od)/2 - dr/2, h=t*0.9),
                    translate([0,0,-1])(
                        cylinder(r=float(ind)/2+dr/2, h=t+2),
                    )
                )
            )
        )
        return u

    


def linear_bearing_block_sc10uu():
    pts = [
        [40.0, 0.0],
        [40.0, 6.0],
        [39.0, 7.0],
        [39.0, 21.0],
        [32.0, 21.0],
        [27.0, 26.0],
        ]
        
    pts = pts + mirror_points_x(pts, 20.0)

    pts = shift_points(pts, [-20.0, -13.0])

    u = linear_extrude(35.0)(polygon(pts))

    u = difference()(
        u,
        translate([0,0,-1])(
            cylinder(r=5.0, h=37.0)
        ),
        translate([-14.0, -15.0, 35.0/2-10.5])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=40.0)
            )
        ),
        translate([-14.0, -15.0, 35.0/2+10.5])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=40.0)
            )
        ),
        translate([14.0, -15.0, 35.0/2-10.5])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=40.0)
            )
        ),
        translate([14.0, -15.0, 35.0/2+10.5])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=40.0)
            )
        )
    )
    
    return color(aluminium_colour)(u)

def sbr12(l, h = 20.46):
    
    pts = [
        [34.0/2, 0.0],
        [34.0/2, 4.5],
        [15.0/2, 4.5],
        [6.0/2, 15.0],        
        ]
        
    pts = pts + mirror_points_x(pts, 0.0)

    pts = shift_points(pts, [0.0, -h])

    u = linear_extrude(l)(polygon(pts))

    u = u + cylinder(r=12.0/2, h=l)

    return color(steel_colour)(u)

class SBR12(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
            'height_above_mounting_plane' : 20.46
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'SBR12', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return sbr12(self.get_data('length'),
                     h=self.get_data('height_above_mounting_plane'))


def sbr12uu():
    pts = [
        [8.5/2, 7.0],
        [8.5/2+3, 0.0],
        [40.0/2, 0.0],
        [40.0/2, 27.6],
    ]
    
    pts = pts + mirror_points_x(pts, 0.0)

    pts = shift_points(pts, [0.0, -27.6+17.0])
    
    u = linear_extrude(39.0, convexity=4)(polygon(pts))

    u = difference()(
        u,
        translate([0,0,-1])(cylinder(r=12.0/2, h=41.0)),
        translate([14.0, 27.6-17.0-1, 39.0/2+13.0])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=11.0)
            )
        ),
        translate([14.0, 27.6-17.0-1, 39.0/2-13.0])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=11.0)
            )
        ),
        translate([-14.0, 27.6-17.0-1, 39.0/2+13.0])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=11.0)
            )
        ),
        translate([-14.0, 27.6-17.0-1, 39.0/2-13.0])(
            rotate([-90, 0, 0])(
                cylinder(r=5.0/2, h=11.0)
            )
        )
    )
    u = translate([0.0, 0.0, -39.0/2])(
        u
    )
    return color(aluminium_colour)(u)

class SBR12UU(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'SBR12UU', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return sbr12uu()

def sfu1204_screw(l, show_thread=False):
    thread_len = l - 15 - 39 - 10
    if show_thread:
        section = screw_thread.default_thread_section(tooth_height=6,
                                                      tooth_depth=1)
        s = screw_thread.thread(outline_pts=section, inner_rad=10.0/2,
                                pitch=4.0, length=thread_len,
                                segments_per_rot=12)
    else:
        s = cylinder(r=12.0/2,
                     h=thread_len)
    u = union()(
        cylinder(r=8.0/2,
                 h=l),
        translate([0.0, 0.0, 15.0])(
            cylinder(r=10.0/2,
                     h=l - 15 - 10)
        ),
        translate([0,0,15.0+39.0])(
            s
        )
    )
    return color(Steel)(u)

class SFU1204Screw(AssemblyBase):
    def __init__(self, data={}):
        defaults = {            
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'SFU1204Screw', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return sfu1204_screw(self.get_data('length'))

def sfu1204_nut(show_thread=False):
    u = union()(
        cylinder(r=42.0/2, h=8.0),
        translate([0,0,-10.0])(
            cylinder(r=22.0/2,
                     h = 10.0 + 0.1)
        ),
        translate([0,0,8.0-35.0])(
            cylinder(r=21.8/2,
                     h=35.0 - 10.0 - 8.0 + 0.1)
        )
    )


    drill = translate([0.0,16.0,-0.6])(cylinder(r=4.5/2, h=10.0))
    h1 = 30.0
    u = difference()(
        u,
        translate([h1/2,-15,-1])(
            cube([30, 30, 30])
        ),
        translate([-h1/2-30,-15,-1])(
            cube([30, 30, 30])
        ),
        translate([0,0,-50])(
            cylinder(r=12.0/2,
                     h=60)
        ),
        drill,
        rotate([0,0,45])(drill),
        rotate([0,0,-45])(drill),
        rotate([0,0,180])(drill),
        rotate([0,0,180-45])(drill),
        rotate([0,0,180+45])(drill),
    )
    return color(Steel)(u)

class SFU1204Nut(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'SFU1204Nut', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return sfu1204_nut()


def lm12uu():
    u = difference()(
        cylinder(r=21.0/2, h=30.0),
        translate([0,0,-1])(
            cylinder(r=12.0/2, h=32.0)
        )
    )
    return color(Steel)(u)

class LM12UU(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'LM12UU', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return lm12uu()

def lm12luu():
    u = difference()(
        cylinder(r=21.0/2, h=57.0),
        translate([0,0,-1])(
            cylinder(r=12.0/2, h=57.0+2)
        )
    )
    return color(Steel)(u)

def lm10uu():
    u = difference()(
        cylinder(r=19.0/2, h=29.0),
        translate([0,0,-1])(
            cylinder(r=10.0/2, h=31.0)
        )
    )
    return color(Steel)(u)

class LM10UU(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'LM10UU', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return lm10uu()

    

def nema(size=23, l=76.0, shaft_dia=8.0):
    if size == 23:
        w = 57.0
    else:
        raise NotImplementedError

    return union()(
        color(Black)(
            translate([-w/2,-w/2,-l])(
                cube([w,w,l])
            ),
        ),
        color(Steel)(
            cylinder(r=shaft_dia/2, h=21.0)
        )
    )


def bk10():
    return color(Black)(
        difference()(
            union()(
                translate([-22.0, -30.0, 0.0])(
                    cube([32.5, 60.0, 25.0])
                ),
                translate([-34.0/2, -34.0/2, 0.0])(
                    cube([34.0, 34.0, 30.0])
                )
            ),
            translate([0,0,-1])(
                cylinder(r=10.0/2, h=32.0)
            ),
            translate([-22.0, -46.0/2, -13.0/2+25.0/2])(
                rotate([0,90,0])(
                    translate([0,0,-1])(
                        cylinder(r=5.5/2, h=39+1)
                    )
                )
            ),
            translate([-22.0, -46.0/2, 13.0/2+25.0/2])(
                rotate([0,90,0])(
                    translate([0,0,-1])(
                        cylinder(r=5.5/2, h=39+1)
                    )
                )
            ),
            translate([-22.0, 46.0/2, -13.0/2+25.0/2])(
                rotate([0,90,0])(
                    translate([0,0,-1])(
                        cylinder(r=5.5/2, h=39+1)
                    )
                )
            ),
            translate([-22.0, 46.0/2, 13.0/2+25.0/2])(
                rotate([0,90,0])(
                    translate([0,0,-1])(
                        cylinder(r=5.5/2, h=39+1)
                    )
                )
            )
            
        )
    )

class BK10Bearing(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'BK10', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return bk10()


def bf10():
    return color(Black)(
        difference()(
            union()(
                translate([-22.0, -30.0, 0.0])(
                    cube([32.5, 60.0, 20.0])
                ),
                translate([-34.0/2, -34.0/2, 0.0])(
                    cube([34.0, 34.0, 20.0])
                )
            ),
            translate([0,0,-1])(
                cylinder(r=8.0/2, h=22.0)
            ),
            translate([-22.0, 46.0/2, 20.0/2])(
                rotate([0,90,0])(
                    translate([0,0,-1])(
                        cylinder(r=5.5/2, h=39+1)
                    )
                )
            ),
            translate([-22.0, -46.0/2, 20.0/2])(
                rotate([0,90,0])(
                    translate([0,0,-1])(
                        cylinder(r=5.5/2, h=39+1)
                    )
                )
            )
        )
    )

class BF10Bearing(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'BF10', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return bf10()


def fk10():
    return color(Black)(
        difference()(
            union()(
                translate([-42.0/2, -42.0/2, 17.0])(
                    cube([42.0, 42.0, 10.0])
                ),
                cylinder(r=34.0/2, h=17.0 + 1.0)
            ),
            translate([0,0,-1])(
                cylinder(r=10.0/2, h=29.0)
            ),
            rotate([0,0,45])(
                translate([42.0/2, 0, 16])(
                    cylinder(r=4.0/2, h=14.0)
                )
            ),
            rotate([0,0,45+90])(
                translate([42.0/2, 0, 16])(
                    cylinder(r=4.0/2, h=14.0)
                )
            ),
            rotate([0,0,45+180])(
                translate([42.0/2, 0, 16])(
                    cylinder(r=4.0/2, h=14.0)
                )
            ),
            rotate([0,0,45+270])(
                translate([42.0/2, 0, 16])(
                    cylinder(r=4.0/2, h=14.0)
                )
            )
        )
    )

class FK10Bearing(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'FK10', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return fk10()


def ff10():
    return color(Black)(
        difference()(
            union()(
                translate([-35.0/2, -35.0/2, 5.0])(
                    cube([35.0, 35.0, 7.0])
                ),
                cylinder(r=28.0/2, h=5.0 + 1.0)
            ),
            translate([0,0,-1])(
                cylinder(r=8.0/2, h=14.0)
            ),
            rotate([0,0,45])(
                translate([35.0/2, 0, -1])(
                    cylinder(r=4.0/2, h=14.0)
                )
            ),
            rotate([0,0,45+90])(
                translate([35.0/2, 0, -1])(
                    cylinder(r=4.0/2, h=14.0)
                )
            ),
            rotate([0,0,45+180])(
                translate([35.0/2, 0, -1])(
                    cylinder(r=4.0/2, h=14.0)
                )
            ),
            rotate([0,0,45+270])(
                translate([35.0/2, 0, -1])(
                    cylinder(r=4.0/2, h=14.0)
                )
            )
        )
    )

class FF10Bearing(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'FF10', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return ff10()


    
def gt2_pulley(nt, shaft_dia=8.0, belt_width=6.0):
    d = nt * 2 / math.pi
    ed = 16 / 12.7 * d
    hub_h = 8.0
    u = union()(
        cylinder(r=ed/2, h=hub_h),
        translate([0.0, 0.0, hub_h-0.5])(
            cylinder(r=d/2, h=belt_width+1+1.0)
        ),
        translate([0.0, 0.0, hub_h + belt_width + 1])(
            cylinder(r=ed/2, h=1.0),
        )
    )

    u = difference()(
        u,
        translate([0,0,-1])(
            cylinder(r=shaft_dia/2, h=hub_h + belt_width + 2)
        )
    )
    return color(aluminium_colour)(u)

def sk12():
    u = union()(
        translate([-20.0/2, -23, 0.0])(
            cube([20.0, 37.5, 14.0])
        ),
        translate([-42.0/2, -23, 0.0])(
            cube([42.0, 6.0, 14.0])
        )
    )
    u = difference()(
        u,
        translate([0,0,-1])(
            cylinder(r=12.0/2, h=16)
        ),
        translate([-32.0/2, -23.0+7, 14.0/2])(
            rotate([90,0,0])(
                cylinder(r=5.5/2, h=8)
            )
        ),
        translate([32.0/2, -23.0+7, 14.0/2])(
            rotate([90,0,0])(
                cylinder(r=5.0/2, h=8)
            )
        ),
    )
    return color(aluminium_colour)(u)

class SK12(AssemblyBase):
    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, 'SK12', defaults)
        
    def calculate(self):
        return True

    def generate(self):
        return sk12()


class SFU1204ScrewAssembly(AssemblyBase):
    
    def __init__(self, data={}):
        defaults = {
            'fixed_nut_type' : 'bk',
            'floating_nut_type' : 'bf',
            'length' : 300.0
        }
        defaults.update(data)
        AssemblyBase.__init__(self, "SFU1204ScrewAssembly", defaults)

    def calculate(self):
        self.data['screw_len'] = self.data['length']
        self.data['screw_fixed_pos'] = 39.0 + 15.0
        self.data['screw_float_pos'] = self.data['screw_len'] - 10.0
        self.screw = SFU1204Screw({'length' : self.data['screw_len']})
        self.add_child(self.screw)
        
        if self.data['fixed_nut_type'] == 'bk':
            self.fixed_nut = BK10Bearing()
        elif self.data['fixed_nut_type'] == 'fk':
            self.fixed_nut = FK10Bearing()
            self.data['screw_input_bearing_mounting_face'] = \
                                  self.data['screw_fixed_pos'] - 10
        else:
            raise NotImplementedError

        self.add_child(self.fixed_nut)

        if self.data['floating_nut_type'] == 'bf':
            self.floating_nut = BF10Bearing()
        elif self.data['floating_nut_type'] == 'ff':
            self.floating_nut = FF10Bearing()
            self.data['screw_end_bearing_mounting_face'] = \
                         self.data['screw_float_pos'] + 7
        else:
            raise NotImplementedError
        self.add_child(self.floating_nut)

        return True
        
    def generate(self):
        if self.data['fixed_nut_type'] == 'bk':
            kn = translate([0,0,self.data['screw_fixed_pos']-30])(
                self.fixed_nut.generate()
            )
        elif self.data['fixed_nut_type'] == 'fk':
            kn = translate([0,0,self.data['screw_fixed_pos']-27])(
                self.fixed_nut.generate()
            )
        else:
            raise NotImplementedError
        
        if self.data['floating_nut_type'] == 'bf':
            fn = translate([0,0,self.data['screw_float_pos']])(
                self.floating_nut.generate()
            )
        elif self.data['floating_nut_type'] == 'ff':
            fn = translate([0,0,self.data['screw_float_pos']+12.0])(
                mirror([0,0,1])(
                    self.floating_nut.generate()
                ))
        else:
            raise NotImplementedError

        return self.screw.generate() + kn + fn
    

class MetricNut(AssemblyBase):

    def __init__(self, data={}):
        defaults = {
        }
        defaults.update(data)
        AssemblyBase.__init__(self, "M%dNut" % defaults['thread_size'],
                              defaults)

    
    def calculate(self):        
        self.inner_r = float(self.data['thread_size'])/2
        code = int(float(self.data['thread_size'] * 10) + 0.5)
        self.outer_r = {
            16 : 3.41,
            20 : 4.32,
            25 : 5.45,
            30 : 6.01,
            40 : 7.66,
            50 : 8.79,
            60 : 11.05,
            80 : 14.38,
            100 : 17.77,
            120 : 20.03,
            140 : 23.35,
            160 : 26.75,
            200 : 32.95
        }[code] / 2
        self.height = {
            16 : 1.3,
            20 : 1.6,
            25 : 2.0,
            30 : 2.4,
            40 : 3.2,
            50 : 4.7,
            60 : 5.2,
            80 : 6.8,
            100 : 8.4,
            120 : 10.8,
            140 : 12.8,
            160 : 14.8,
            200 : 18.0
        }[code]
        return True
        
    def generate(self):
        return color(Steel)(
            difference()(
                cylinder(r=self.outer_r, h=self.height,
                         segments=6),
                translate([0,0,-1])(
                    cylinder(r=self.inner_r, h=self.height+2)
                )
            )
        )
