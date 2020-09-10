from abc import ABC, abstractmethod
import math
import pdb

from instruction import *

class Optimizer(ABC):
    def __init__(self, instructions, opts):

        self.name2pt = dict()
        self.losses = dict()
        self.has_loss = False
        self.opts = opts
        self.instructions = instructions

        super().__init__()

        # self.preprocess()

    def preprocess(self):
        for i in self.instructions:
            self.process_instruction(i)

    def process_instruction(self, i):
        if isinstance(i, Sample):
            self.sample(i)
        elif isinstance(i, Compute):
            self.compute(i)
        elif isinstance(i, Parameterize):
            self.parameterize(i)
        else:
            raise NotImplementedError("FIXME: Finish process_instruction")

    @abstractmethod
    def get_point(self, x, y):
        pass

    def lookup_pts(self, ps):
        return [self.name2pt[p] for p in ps]

    @abstractmethod
    def mkvar(self, name, shape=[], lo=-1.0, hi=1.0, trainable=None):
        pass

    @abstractmethod
    def register_pt(self, p, P):
        pass

    @abstractmethod
    def register_loss(self, key, var, weight=1.0):
        pass


    @abstractmethod
    def regularize_points(self):
        pass

    @abstractmethod
    def make_points_distinct(self):
        pass

    # FIXME: The below should be combined with an abstract Point class

    #####################
    ## Math Utilities
    ####################
    @abstractmethod
    def addV(self, x, y):
        pass

    @abstractmethod
    def subV(self, x, y):
        pass

    @abstractmethod
    def negV(self, x):
        pass

    @abstractmethod
    def sumVs(self, xs):
        pass

    @abstractmethod
    def mulV(self, x, y):
        pass

    @abstractmethod
    def divV(self, x, y):
        pass

    @abstractmethod
    def powV(self, x, y):
        pass

    @abstractmethod
    def sqrtV(self, x):
        pass

    @abstractmethod
    def sinV(self, x):
        pass

    @abstractmethod
    def cosV(self, x):
        pass

    @abstractmethod
    def acosV(self, x):
        pass

    @abstractmethod
    def tanhV(self, x):
        pass

    @abstractmethod
    def sigmoidV(self, x):
        pass

    @abstractmethod
    def constV(self, x):
        pass

    #####################
    ## Sample
    ####################

    def sample(self, i):
        s_method = i.sampler
        s_args = i.args
        if s_method == "uniform": self.sample_uniform(i.points)
        elif s_method == "polygon": self.sample_polygon(i.points)
        elif s_method == "triangle": self.sample_triangle(i.points)
        elif s_method == "isoTri": self.sample_triangle(i.points, iso=args[0])
        elif s_method == "acuteTri": self.sample_triangle(i.points, acute=True)
        elif s_method == "acuteIsoTri": self.sample_triangle(i.points, iso=args[0], acute=True)
        elif s_method == "rightTri": self.sample_triangle(i.points, right=args[0])
        elif s_method == "equiTri": self.sample_triangle(i.points, equi=True)
        else: raise NotImplementedError(f"[sample] NYI: Sampling method {s_method}")

    def sample_uniform(self, ps):
        [p] = ps
        P   = self.get_point(x=self.mkvar(p+"x"), y=self.mkvar(p+"y"))
        self.register_pt(p, P)


    def sample_polygon(self, ps):
        if len(ps) < 4:
            print("WARNING: sample_polygon expecting >3 points")

        angle_zs = [self.mkvar(name=f"polygon_angle_zs_{i}") for i in range(len(ps))]
        multiplicand = ((len(ps) - 2) / len(ps)) * math.pi + (math.pi / 3)
        angles = [self.mulV(multiplicand, self.tanhV(self.mulV(0.2, az))) for az in angle_zs]

        scale_zs = [self.mkvar(name=f"polygon_scale_zs_{i}") for i in range(len(ps))]
        scales = [self.mulV(0.5, self.tanhV(self.mulV(0.2, sz))) for sz in scale_zs]

        Ps = [self.get_point(self.constV(-2.0), self.constV(0.0)),
              self.get_point(self.constV(2.0), self.constV(0.0))]
        s = self.dist(Ps[0], Ps[1])

        for i in range(2, len(ps) + 1):
            A, B = Ps[-2:]
            X = B + self.rotate_counterclockwise(self.negV(angles[i-1]), A - B)
            scale = self.divV(self.mulV(s, self.addV(1, scales[i-1])), self.dist(X, B))
            P = B + (X - B).smul(scale)
            Ps.append(P)

        # Angles should sum to (n-2) * pi
        angle_sum = self.sumVs(angles)
        expected_angle_sum = math.pi * (len(ps) - 2)
        self.register_loss("polygon-angle-sum", self.subV(angle_sum, expected_angle_sum), weight=1e-1)

        # First point shoudl equal the last point
        self.register_loss("polygon-first-eq-last", self.dist(Ps[0], Ps[len(ps)]), weight=1e-2)

        # First angle should be the one sampled (known to be <180)
        self.register_loss("polygon-first-angle-eq-sampled",
                           self.subV(angles[0], self.angle(Ps[-1], Ps[0], Ps[1])),
                           weight=1e-2)


        for p, P in zip(ps, Ps[:-1]):
            self.register_pt(p, P)


    def sample_triangle(self, ps, iso=None, right=None, acute=False, equi=False):
        if not (iso or right or acute or equi):
            return self.sample_polygon(ps)

        [nA, nB, nC] = ps
        B = self.get_point(self.constV(-2.0), self.constV(0.0))
        C = self.get_point(self.constV(2.0), self.constV(0.0))

        if iso is not None or equi:
            Ax = self.constV(0.0)
        else:
            Ax = self.mkvar("tri_x", lo=-1.0, hi=1.2)

        if right is not None:
            Ay = self.sqrtV(self.subV(4, self.powV(Ax, 2)))
        elif equi:
            Ay = self.mulV(2, self.sqrtV(self.constV(3)))
        else:
            AyLo = 1.1 if acute else 0.4
            z = mkvar("tri")
            Ay = self.addV(self.constV(AyLo), self.mulV(3.0, self.sigmoidV(z)))

        A = self.get_point(Ax, Ay)

        # Shuffle if the isosceles vertex was not C
        if iso == nB or right == nB:   (A, B, C) = (B, A, C)
        elif iso == nC or right == nC: (A, B, C) = (C, B, A)

        self.register_pt(nA, A)
        self.register_pt(nB, B)
        self.register_pt(nC, C)



    #####################
    ## Compute
    ####################

    def compute(self, i):
        if i.computation[0] == "midp":
            self.compute_midp(i.point, i.computation[1])
        else:
            raise NotImplementedError("FIXME: Finish compute")

    def compute_midp(self, m, ps):
        A, B = self.lookup_pts(ps)
        M = self.midp(A, B)
        self.register_pt(m, M)
        # self.name2pt[m] = M


    #####################
    ## Parameterize
    ####################

    def parameterize(self, i):
        param_method = i.parameterization
        if param_method == "coords":
            self.parameterize_coords(i.point)
        else:
            raise NotImplementedError("FIXME: Finish parameterize")

    def parameterize_coords(self, p):
        self.sample_uniform([p])

    #####################
    ## Comp. Geo
    ####################

    def midp(self, A, B):
        return (A + B).smul(0.5)

    def sqdist(self, A, B):
        xdiff = self.subV(A.x, B.x)
        ydiff = self.subV(A.y, B.y)
        return self.addV(self.powV(xdiff, 2), self.powV(ydiff, 2))

    def dist(self, A, B):
        return self.powV(self.sqdist(A,B), 0.5)

    def inner_product(self, A, B):
        a1, a2 = A
        b1, b2 = B
        return self.addV(self.mulV(a1, b1), self.mulV(a2, b2))

    def matrix_mul(self, mat, pt):
        pt1, pt2 = mat
        return self.get_point(self.inner_product(pt1, pt), self.inner_product(pt2, pt))

    def rotation_matrix(self, theta):
        r1 = self.get_point(self.cosV(theta), self.negV(self.sinV(theta)))
        r2 = self.get_point(self.sinV(theta), self.cosV(theta))
        return (r1, r2)

    def rotate_counterclockwise(self, theta, pt):
        return self.matrix_mul(self.rotation_matrix(theta), pt)

    def side_lengths(self, A, B, C):
        return self.dist(B, C), self.dist(C, A), self.dist(A, B)

    def angle(self, A, B, C):
        a, b, c = self.side_lengths(A, B, C)
        num = self.subV(self.addV(self.powV(a, 2), self.powV(c, 2)), self.powV(b, 2))
        denom = self.mulV(self.mulV(a, 2), c)
        return self.acosV(self.divV(num, denom))

    def conway_vals(self, A, B, C):
        a, b, c = self.side_lengths(A, B, C)

        def cv_aux(x1, x2, x3):
            num = self.subV(self.addV(self.powV(x1, 2), self.powV(x2, 2)), self.powV(x3, 2)) # x1**2 + x2**2 - x3**2
            return self.divV(num, 2)

        return cv_aux(b, c, a), cv_aux(c, a ,b), cv_aux(a, b, c)

    def trilinear(self, A, B, C, x, y, z):
        a, b, c = self.side_lengths(A, B, C)
        denom = self.addV(
            self.addV(self.mulV(a, x), self.mulV(b, y)),
            self.mulV(c, z)) # a * x + b * y + c * z
        xnum = self.addV(
            self.addV(
                self.mulV(self.mulV(a, x), A.x),
                self.mulV(self.mulV(b, y), B.x)),
            self.mulV(self.mulV(c, z), C.x))
        ynum = self.addV(
            self.addV(
                self.mulV(self.mulV(a, x), A.y),
                self.mulV(self.mulV(b, y), B.y)),
            self.mulV(self.mulV(c, z), C.y))
        return self.get_point(self.divV(xnum, 2), self.divV(ynum, 2))

    def barycentric(self, A, B, C, x, y, z):
        a, b, c = self.side_lengths(A, B, C)
        return self.trilinear(A, B, C, self.divV(x, a), self.divV(y, b), self.divV(z, c))

    def circumcenter(self, A, B, C):
        a, b, c = self.side_lengths(A, B, C)
        Sa, Sb, Sc = self.conway_vals(A, B, C)
        res = self.barycentric(A, B, C,
                               self.mulV(self.powV(a, 2), Sa),
                               self.mulV(self.powV(b, 2), Sb),
                               self.mulV(self.powV(c, 2), Sc))
        return res

    def orthocenter(self, A, B, C):
        a, b, c = self.side_lengths(A, B, C)
        Sa, Sb, Sc = self.conway_vals(A, B, C)
        res = self.barycentric(A, B, C,
                               self.mulV(Sb, Sc),
                               self.mulV(Sc, Sa),
                               self.mulV(Sa, Sb))
        return res

    def centroid(self, A, B, C):
        return self.barycentric(A, B, C, 1, 1, 1)

    def incenter(self, A, B, C):
        return self.trilinear(A, B, C, 1, 1, 1)
