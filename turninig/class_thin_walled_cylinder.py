from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import math
import tempfile
import sys
import os
import argparse
import math
import numpy as np

    
executeOnCaeStartup()
Mdb()
model = mdb.models['Model-1']
OX = (1, 0, 0)
OY = (0, 1, 0)
OZ = (0, 0, 1)

def N(value):
    return value;

def m(value):
    return value

def mm(value): # gets mm, returns m
    return value * 1e-3

def cm(value):
    return value * 1e-2

def rad(rad_value): # gets radians, returns radians
    return rad_value

def deg(value): # gets degrees, return radians
    return (value * pi)/180

def cart2pol(x, y):
    rho = np.sqrt(x**2 + y**2)
    phi = np.arctan2(y, x)
    return(rho, math.degrees(phi))

def pol2cart(rho, phi):
    phi = math.radians(phi)
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    return(x, y)   

def rotate(point, axis, theta):
    """
    Return the rotation matrix associated with counterclockwise rotation about
    the given axis by theta radians.
    """
    def rotation_matrix(axis, theta):
        axis = np.asarray(axis)
        axis = axis / math.sqrt(np.dot(axis, axis))
        a = math.cos(theta / 2.0)
        b, c, d = -axis * math.sin(theta / 2.0)
        aa, bb, cc, dd = a * a, b * b, c * c, d * d
        bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
        return np.array([[aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)], [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)], [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc]])
    return tuple(np.dot(rotation_matrix(axis, theta), point))
    


class MaterialExplicit:

    def __init__(self, name, density, young, poisson, A, B, n, d1, d2, d3, ref_strain_rate, disp_at_failure):
        self.name = name
        mdb.models['Model-1'].Material(name=name)
        self.material = mdb.models['Model-1'].materials[name]
        self.material.Density(table=((density, ), ))
        self.material.Elastic(table=((young, poisson), ))
        self.material.Plastic(hardening=JOHNSON_COOK, table=((A, B, n, 0.0, 0.0, 0.0), ))
        self.material.JohnsonCookDamageInitiation(table=((d1, d2, d3, 0.0, 0.0, 0.0, 0.0, ref_strain_rate), ))
        self.material.johnsonCookDamageInitiation.DamageEvolution(type=DISPLACEMENT, table=((disp_at_failure, ), ))



class Material:

    def __init__(self, name, young, poisson):
        self.name = name
        model.Material(name=name)
        model.materials[name].Elastic(table=((young, poisson), ))
        self.material =  model.materials[name]



class InteractionProperty:

    def __init__(self):
        self.name = "Interaction-Property"
        model.ContactProperty(self.name)
        model.interactionProperties[self.name].TangentialBehavior(formulation=ROUGH)
        model.interactionProperties[self.name].NormalBehavior(
            pressureOverclosure=HARD, allowSeparation=OFF, contactStiffness=DEFAULT, 
            contactStiffnessScaleFactor=1.0, clearanceAtZeroContactPressure=0.0, 
            stiffnessBehavior=LINEAR, constraintEnforcementMethod=PENALTY)



class Step:

    def __init__(self, name, previous='Initial'):
        self.name = name
        model.StaticStep(name=name, previous=previous)



class Workpiece:

    def __init__(self, length, inner, outer, p_num):
        self.name = "Workpiece"
        self.length = length
        self.inner = inner
        self.outer = outer
        self.p_num = p_num

        sketch = model.ConstrainedSketch(name=self.name + '-profile', sheetSize=0.1)
        sketch.sketchOptions.setValues(decimalPlaces=3)
        sketch.setPrimaryObject(option=STANDALONE)
        sketch.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(0.0, self.inner))
        sketch.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(0.0, self.outer))
        model.Part(name=self.name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
        self.part = model.parts[self.name]
        self.part.BaseSolidExtrude(sketch=sketch, depth=self.length)
        sketch.unsetPrimaryObject()

    def set_section(self, section):
        region = self.part.Set(cells=self.part.cells, name='Material-region')
        self.part.SectionAssignment(region=region, sectionName=section.name, offset=0.0, 
            offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)

    def mesh(self, size=0.0015, deviationFactor=0.1, minSizeFactor=0.1):
        self.part.setMeshControls(regions=self.part.cells, technique=SWEEP, algorithm=MEDIAL_AXIS)
        self.part.seedPart(size=size, deviationFactor=deviationFactor, minSizeFactor=minSizeFactor)
        self.part.generateMesh()

    def partition(self):
        for p in range(0, self.p_num):
            try:
                self.part.PartitionCellByPlaneThreePoints(cells=self.part.cells, 
                    point1=(0, 0, 0), 
                    point2=(0, 0, 1),
                    point3=rotate(point=(0, 1, 0), axis=OZ, theta = deg(p * 360/self.p_num)))
            except:
                pass



class Jaw:

    def __init__(self, length, width, height):
        self.name = "Jaw"
        self.length = length
        self.width = width
        self.height = height
        sketch = model.ConstrainedSketch(name='-profile', sheetSize=0.1) 
        sketch.sketchOptions.setValues(decimalPlaces=3)
        sketch.setPrimaryObject(option=STANDALONE)
        sketch.rectangle(point1=(-0.5 * length, -0.5 * height), point2=(0.5 * length, 0.5 * height))
        self.part = model.Part(name=self.name, dimensionality=THREE_D,  type=DEFORMABLE_BODY) # 
        self.part.BaseSolidExtrude(sketch=sketch, depth=width)
        sketch.unsetPrimaryObject()

    def set_section(self, section):
        region = self.part.Set(cells=self.part.cells, name='Material-region')
        self.part.SectionAssignment(region=region, sectionName=section.name, offset=0.0, 
            offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)
    
    def partition(self):
        point1 = (0, 0, 0)
        point2 = (1, 0, 0)
        point3 = (0, 0, 1)
        self.part.PartitionCellByPlaneThreePoints(cells=self.part.cells, point1=point1, point2=point2, point3=point3)
            
        point1 = (0, 0, 0)
        point2 = (0, 1, 0)
        point3 = (0, 0, 1)
        self.part.PartitionCellByPlaneThreePoints(cells=self.part.cells, point1=point1, point2=point2, point3=point3)

    def mesh(self, size=0.0015, deviationFactor=0.1, minSizeFactor=0.1):
        self.part.setMeshControls(regions=self.part.cells, technique=SWEEP, algorithm=MEDIAL_AXIS)
        self.part.seedPart(size=size, deviationFactor=deviationFactor, minSizeFactor=minSizeFactor)
        self.part.generateMesh()



class Assembly:
    
    class Jaw:

        def __init__(self, index, name):
            self.index = index
            self.name = name
            self.angle = 360/3 * (1-index)
            self.CSYS = None

        def __hash__(self):
            return self.index

    def __init__(self, workpiece, jaw, jaw_num, jaw_force):
        self.workpiece = workpiece
        self.jaw = jaw
        self.jaw_force = jaw_force
        self.a = model.rootAssembly
        self.a.DatumCsysByDefault(CARTESIAN)
        self.a.Instance(name=workpiece.name, part=workpiece.part, dependent=ON)
        self.a.Instance(name=jaw.name, part=jaw.part, dependent=ON)
        self.a.rotate(instanceList=(jaw.name, ), axisPoint=(0, 0, 0), axisDirection=OX, angle=rad(-90.0))
        self.a.translate(instanceList=(jaw.name, ), vector=(0, workpiece.outer, 0.5 * jaw.height))
        self.a.RadialInstancePattern(instanceList=(jaw.name, ), point=(0, 0, 0), axis=OZ, number=jaw_num, totalAngle=-360)
        self.a.features.changeKey(fromName=jaw.name, toName=jaw.name+'-rad-1')
        self.assembly_jaws = [Assembly.Jaw(i, 'Jaw-rad-'+str(i)) for i in range(1, 1+jaw_num)]
        self.interactionProperty = InteractionProperty()
        


        region_workpiece=self.a.Surface(side1Faces=self.a.instances[self.workpiece.name].faces, name=jaw.name + '_slave_surf')

        for a_jaw in self.assembly_jaws:
            self._create_CSYS(a_jaw)
            self._create_interaction(a_jaw, region_workpiece, self.interactionProperty)
            self._create_jaw_BSs(a_jaw)
        self.step = Step("Step-1")
        for a_jaw in self.assembly_jaws:
            self._apply_jaw_force(a_jaw, jaw_force)

    def _create_CSYS(self, jaw):
        jaw.CSYS = self.a.DatumCsysByThreePoints(origin=rotate((0, workpiece.outer, 0), OZ, deg(jaw.angle)), 
            point1=(0,0,0), 
            point2=rotate((1, workpiece.outer, 0), OZ, deg(jaw.angle)), 
            name=jaw.name + '_CSYS', coordSysType=CARTESIAN)

    def _create_interaction(self, jaw, region_workpiece, property):
        jaw_instance = self.a.instances[jaw.name]
        workpiece = self.a.instances[self.workpiece.name]
        p1 = rotate((0.25 * self.jaw.length, self.workpiece.outer, 0.25 * self.jaw.height), OZ, deg(jaw.angle))
        p2 = rotate((-0.25 * self.jaw.length, self.workpiece.outer, 0.25 * self.jaw.height), OZ, deg(jaw.angle))
        p3 = rotate((0.25 * self.jaw.length, self.workpiece.outer, 0.75 * self.jaw.height), OZ, deg(jaw.angle))
        p4 = rotate((-0.25 * self.jaw.length, self.workpiece.outer, 0.75 * self.jaw.height), OZ, deg(jaw.angle))

        jaw_faces = jaw_instance.faces.findAt( (p1,),(p2,), (p3,), (p4,), )
        
        region_jaw=self.a.Surface(side1Faces=jaw_faces, name=jaw.name + '_master_surf')       
        
        # # create workpiece master region   
        # def translate_to_workpiece(point):
        #     x, y, z = point
        #     rho, phi = cart2pol(x,y)
        #     x_w, y_w = pol2cart(self.workpiece.outer, phi)
        #     return x_w, y_w, z

        # workpiece_faces = workpiece.faces.findAt( (translate_to_workpiece(p1),),(translate_to_workpiece(p2),), (translate_to_workpiece(p3),), (translate_to_workpiece(p4),), )
        # region_workpiece=self.a.Surface(side1Faces=workpiece_faces, name=jaw.name + '_slave_surf')

        model.SurfaceToSurfaceContactStd(name='Interaction-'+jaw.name, 
            createStepName='Initial', master=region_jaw, slave=region_workpiece, sliding=FINITE, 
            thickness=ON, interactionProperty=property.name, adjustMethod=NONE, 
            initialClearance=OMIT, datumAxis=None, clearanceRegion=None)

    def _create_jaw_BSs(self, jaw):
        jaw_instance = self.a.instances[jaw.name]
        
        jaw_faces = jaw_instance.faces.findAt(
            (rotate((0.25 * self.jaw.length, self.workpiece.outer + 0.5* self.jaw.width, 0), OZ, deg(jaw.angle)),),
            (rotate((-0.25 * self.jaw.length, self.workpiece.outer + 0.5* self.jaw.width, 0), OZ, deg(jaw.angle)),),
            )
        
        region = self.a.Set(faces = jaw_faces, name='Jaw_BS_set-'+jaw.name)
        
        datum = self.a.datums[jaw.CSYS.id]
        model.DisplacementBC(name='BC-'+jaw.name, createStepName='Initial', 
            region=region, u1=UNSET, u2=SET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET, 
            amplitude=UNSET, distributionType=UNIFORM, fieldName='', localCsys=datum)

    def _apply_jaw_force(self, jaw, value):
        vertices = self.a.instances[jaw.name].vertices
        verts1 = vertices.getSequenceFromMask(mask=('[#1 ]', ), ) # hack, replace it with findAt
        region = self.a.Set(vertices=verts1, name='Jaw-force-region-'+jaw.name)        
        datum = self.a.datums[jaw.CSYS.id]
        model.ConcentratedForce(name='Load-'+jaw.name, createStepName=self.step.name, 
            region=region, cf1=value, distributionType=UNIFORM, field='', localCsys=datum)
   


if __name__ == "__main__":
    jaw_num = 3
    steel = Material('Steel', 210e15, 0.29)
    steel_section = model.HomogeneousSolidSection(name='Steel-section', material=steel.name, thickness=None)

    aluminum = Material('Aluminum', 0.7e9, 0.28)
    aluminum_section = model.HomogeneousSolidSection(name='Aluminum-section', material=aluminum.name, thickness=None)

    print(jaw_num)
    workpiece = Workpiece(length=mm(60), inner=mm(59/2), outer=mm(68/2), p_num=jaw_num)
    workpiece.set_section(aluminum_section)
    workpiece.partition()
    workpiece.mesh()

    jaw = Jaw(length=mm(15), width=mm(15), height=mm(15))
    jaw.set_section(steel_section)
    jaw.partition()
    jaw.mesh()

    assembly = Assembly(workpiece, jaw, jaw_num, N(1000))

    a = mdb.models['Model-1'].rootAssembly
    session.viewports['Viewport: 1'].setValues(displayedObject=a)
    session.viewports['Viewport: 1'].view.setValues(session.views['Iso'])