import sys
import os
import math
from solid import *
from solid.utils import *
from solid import screw_thread

aluminium_colour = [0.77, 0.77, 0.8]
steel_colour = [0.7, 0.7, 0.7]#[0.8, 0.8, 0.8]



class AssemblyBase(object):

    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.parent = None
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        child.set_parent(self)

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
        
    def generate(self):
        raise NotImplementedError, "Should be overridden"


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

def sbr12(l):
    
    pts = [
        [34.0/2, 0.0],
        [34.0/2, 4.5],
        [15.0/2, 4.5],
        [6.0/2, 15.0],        
        ]
        
    pts = pts + mirror_points_x(pts, 0.0)

    pts = shift_points(pts, [0.0, -20.46])

    u = linear_extrude(l)(polygon(pts))

    u = u + cylinder(r=12.0/2, h=l)

    return color(steel_colour)(u)

def sbr12uu():
    pts = [
        [8.5/2, 7.0],
        [8.5/2+3, 0.0],
        [40.0/2, 0.0],
        [40.0/2, 27.6],
    ]
    
    pts = pts + mirror_points_x(pts, 0.0)

    pts = shift_points(pts, [0.0, -27.6+17.0])
    
    u = linear_extrude(39.0)(polygon(pts))

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
        )
    )
    return color(Steel)(u)

def lm12uu():
    u = difference()(
        cylinder(r=21.0/2, h=30.0),
        translate([0,0,-1])(
            cylinder(r=12.0/2, h=32.0)
        )
    )
    return color(Steel)(u)

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
