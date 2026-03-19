import bpy, bmesh
from .utils.PyBinaryReader.binary_reader import *
from bpy_extras.io_utils import ImportHelper, axis_conversion
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, FloatProperty
from bpy.types import Operator
from mathutils import Matrix, Vector, Quaternion, Euler
from math import radians, pi, tan
import numpy as np
import os
import tempfile
from .mib import *
from .msb import *

from time import perf_counter
bl_info = {
    "name" : "MSB Model Importer",
    "author" : "Al-Hydra",
    "description" : "Importer for MSB Model format",
    "blender" : (4, 5, 0),
    "version" : (1, 0, 0),
    "category" : "Import"
}


class MSB_IMPORTER_OT_IMPORT(Operator, ImportHelper):
    bl_label = "Import MSB Model (.msb)"
    bl_idname = "import_scene.msb"


    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filter_glob: StringProperty(default="*.msb", options={"HIDDEN"}) # type: ignore
    filename_ext = ".msb"
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore

    
    def draw(self, context):
        layout = self.layout

    def execute(self, context):
        time = perf_counter()
        for file in self.files:
            filepath = os.path.join(self.directory, file.name)

            # Import MIB file if it exists
            if os.path.exists(filepath.replace(".msb", ".mib")):
                importMIB(filepath.replace(".msb", ".mib"))
                
            importMSB(filepath)

        self.report({'INFO'}, f"Imported {len(self.files)} files in {perf_counter() - time:.4f} seconds")

        return {'FINISHED'}


class MSB_FH_import(bpy.types.FileHandler):
    bl_idname = "MSB_FH_import"
    bl_label = "File handler for MSB files"
    bl_import_operator = "import_scene.msb"
    bl_file_extensions = ".msb"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
    def draw():
        pass


class MIB_IMPORTER_OT_IMPORT(Operator, ImportHelper):
    bl_label = "Import MIB Texture (.mib)"
    bl_idname = "import_texture.mib"


    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filter_glob: StringProperty(default="*.mib", options={"HIDDEN"}) # type: ignore
    filename_ext = ".mib"
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore

    
    def draw(self, context):
        layout = self.layout

    def execute(self, context):
        time = perf_counter()
        for file in self.files:
            filepath = os.path.join(self.directory, file.name)
            importMIB(filepath)

        self.report({'INFO'}, f"Imported {len(self.files)} MIB files in {perf_counter() - time:.4f} seconds")

        return {'FINISHED'}


class DropMIBOperator(bpy.types.Operator):
    bl_idname = "wm.drop_mib"
    bl_label = "Drop MIB File"

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        importMIB(self.filepath)
        self.report({'INFO'}, f"Imported MIB file: {self.filepath}")
        return {'FINISHED'}


class MIB_FH_import(bpy.types.FileHandler):
    bl_idname = "MIB_FH_import"
    bl_label = "File handler for MIB files"
    bl_import_operator = "wm.drop_mib"
    bl_file_extensions = ".mib"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
    def draw():
        pass


def importMSB(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
        br = BinaryReader(data)
        msb: MSB = br.read_struct(MSB)
        print(f"Imported MSB file: {filepath}")
        print(f"Number of models: {len(msb.models)}")
        print(f"Number of materials: {len(msb.materials)}")
        if msb.skeleton:
            print(f"Skeleton name: {msb.skeleton.name}, Number of bones: {len(msb.skeleton.bones)}")
        else:
            print("No skeleton found in the MSB file.")
        
        msbName = os.path.basename(filepath).replace(".msb", "")
    
    sklObj = None
    if msb.skeleton:
        sklObj = createArmature(msb.skeleton, msbName + "_armature")
    
    # prepare materials for models
    materialsList = []
    for material in msb.materials:
        materialsList.append(createMaterial(material))
    
    for msbModel in msb.models:
        meshObj = createMesh(msbModel, materialsList, sklObj, msb.skeleton)
        if meshObj and sklObj:
            meshObj.parent = sklObj
            meshObj.parent_type = 'BONE'
            meshObj.parent_bone = sklObj.data.bones[msb.skeleton.bones[msbModel.parentBoneIndex].name].name



def createArmature(skeleton: msbSkeleton, name):
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
    armature = bpy.context.object
    armature.name = name
    armature.show_in_front = True
    armature_data = armature.data
    armature_data.display_type = 'STICK'
    armature_data.name = f"{name}"

    upMatrix = axis_conversion(from_forward='-Z', from_up='Y', to_forward='Y', to_up='Z').to_4x4()
    
    for bone_data in skeleton.bones:
        bone = armature_data.edit_bones.new(bone_data.name)
        
        if bone_data.parentIndex != -1:
            bone.parent = armature_data.edit_bones[skeleton.bones[bone_data.parentIndex].name]
        
        finalMatrix = upMatrix @ Matrix(np.array(bone_data.matrix).reshape(4, 4)).transposed().inverted()
        
        bone.head = finalMatrix @ Vector((0, 0, 0))
        bone.tail = finalMatrix @ Vector((0, 0, 1)) 
        bone.matrix = finalMatrix
        #bone.matrix = bone.matrix.transposed()
    
    #do another loop to connect bones
    '''for bone_data in skeleton.bones:
        bone = armature_data.edit_bones[bone_data.name]
        if bone_data.parentIndex != -1 and len(bone.parent.children) == 1:
            bone.parent.tail = Vector(bone.head)'''
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"Created armature: {armature.name} with {len(skeleton.bones)} bones.")

    return armature

def createMaterial(msbMaterial: msbMaterial):
    mat = bpy.data.materials.new(name=msbMaterial.name)
    mat.use_nodes = True
    
    # get the first texture
    if msbMaterial.textures:
        tex_name = msbMaterial.textures[0]
        # find image by name
        img = bpy.data.images.get(f"{tex_name}.dds")
        if img:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            tex_image = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex_image.image = img
            mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_image.outputs['Color'])
    
    print(f"Created material: {mat.name} with texture: {msbMaterial.textures[0] if msbMaterial.textures else 'None'}")

    return mat


def createMesh(msbModel: msbModel, materialsList: list, sklObj, msbSkl: msbSkeleton =None):
    
    mesh = bpy.data.meshes.new(msbModel.name)
    obj = bpy.data.objects.new(msbModel.name, mesh)
    bpy.context.collection.objects.link(obj)
    
    bm = bmesh.new()
    
    vbStart = []
    
    vertices = np.zeros((0, 3), dtype='f4')
    morphVertices = np.zeros((0, 3), dtype='f4')
    normals = np.zeros((0, 3), dtype='f4')
    uv0 = np.zeros((0, 2), dtype='f4')
    uv1 = np.zeros((0, 2), dtype='f4')
    color = np.zeros((0, 4), dtype='f4')
    weights = np.zeros((0, 4), dtype='f4')
    boneIDs = np.zeros((0, 4), dtype='i4')
    for i, vb in enumerate(msbModel.vertexBuffers):
        vb: vertexBufferInfo 
        msbVertices = vb.vertices["position"]
        vertices = np.vstack((vertices, msbVertices))
        
        if "morphPosition" in vb.vertices.dtype.names:
            morphVertices = np.vstack((morphVertices, vb.vertices["morphPosition"]))
        
        if "normal" in vb.vertices.dtype.names:
            normals = np.vstack((normals, vb.vertices["normal"]))
        if "uv0" in vb.vertices.dtype.names:
            uv0 = np.vstack((uv0, vb.vertices["uv0"]))
        if "uv1" in vb.vertices.dtype.names:
            uv1 = np.vstack((uv1, vb.vertices["uv1"]))
        if "color" in vb.vertices.dtype.names:
            color = np.vstack((color, vb.vertices["color"]))
        if "weights" in vb.vertices.dtype.names:
            weights = np.vstack((weights, vb.vertices["weights"]))
        if "boneIDs" in vb.vertices.dtype.names:
            boneIDs = np.vstack((boneIDs, vb.vertices["boneIDs"]))
        
        
        vbStart.append(len(bm.verts))

        verts = [bm.verts.new((v[0], v[1], v[2])) for v in msbVertices]
                
        bm.verts.ensure_lookup_table()
        
    for fb in msbModel.faceBuffers:
        fb: faceBufferInfo
        startIndex = vbStart[fb.bufferIndex]
        materialIndex = fb.materialIndex
        material = materialsList[materialIndex]
        indexType = fb.indexType
        
        # add material to the object if not already present
        if material.name not in obj.data.materials:
            obj.data.materials.append(material)
        matIndex = obj.data.materials.find(material.name)
    
    
        if indexType == 0:  # triangles
            for i in range(0, len(fb.faces), 3):
                idx0 = startIndex + fb.faces[i]
                idx1 = startIndex + fb.faces[i + 1]
                idx2 = startIndex + fb.faces[i + 2]
                
                try:
                    face = bm.faces.new((bm.verts[idx0], bm.verts[idx1], bm.verts[idx2]))
                    face.material_index = matIndex
                    face.smooth = True
                except ValueError:
                    pass  # face already exists
        
        elif indexType == 256:
            # triangle strips
            orientation = True
            for vi in range(len(fb.faces) - 2):
                i0 = fb.faces[vi]
                i1 = fb.faces[vi + 1]
                i2 = fb.faces[vi + 2]

                # Check for degenerate triangle (strip break)
                if i0 == i1 or i1 == i2 or i2 == i0:
                    orientation = not orientation  #flip orientation even on degenerate to maintain correct winding
                    continue

                idx0 = startIndex + i0
                idx1 = startIndex + i1
                idx2 = startIndex + i2
                
                if orientation:
                    face_verts = (bm.verts[idx0], bm.verts[idx1], bm.verts[idx2])
                else:
                    face_verts = (bm.verts[idx1], bm.verts[idx0], bm.verts[idx2])

                try:
                    face = bm.faces.new(face_verts)
                    face.material_index = matIndex
                    face.smooth = True
                except ValueError:
                    pass

                orientation = not orientation
        
        else:
            print(f"Unsupported index type: {indexType} in model: {msbModel.name}")
    
    bm.faces.ensure_lookup_table()

    bm.to_mesh(mesh)
    bm.free()

    # add morph target shape key
    if morphVertices.shape[0] == len(mesh.vertices):
        obj.shape_key_add(name="Basis", from_mix=False)
        morphKey = obj.shape_key_add(name="Morph", from_mix=False)
        morphKey.data.foreach_set("co", morphVertices[:, :3].astype('f4').flatten())
    
    
    if normals.shape[0] == len(mesh.vertices):
        #rearrange normals to match Blender's coordinate system
        #normals[:, [1, 2]] = normals[:, [2, 1]] * np.array([ -1, 1])
        mesh.normals_split_custom_set_from_vertices(normals.tolist())
    
    #prepare loops
    loops = mesh.loops
    loopCount = len(loops)
    loopVertexIndices = np.zeros((loopCount,), dtype='i4')
    loops.foreach_get("vertex_index", loopVertexIndices)

    if uv0.shape[0] == len(mesh.vertices):
        uvLayer0 = mesh.uv_layers.new(name="UVMap0")
        uvData0 = uvLayer0.data
        loopUVs0 = uv0[loopVertexIndices]

        # Flip V coordinate
        loopUVs0[:, 1] = 1 - loopUVs0[:, 1]

        uvLayer0.data.foreach_set("uv", loopUVs0.flatten())
    
    # add uv maps
    if uv1.shape[0] == len(mesh.vertices):
        uvLayer1 = mesh.uv_layers.new(name="UVMap1")
        uvData1 = uvLayer1.data
        loopUVs1 = uv1[loopVertexIndices]

        # Flip V coordinate
        loopUVs1[:, 1] = 1 - loopUVs1[:, 1]

        uvLayer1.data.foreach_set("uv", loopUVs1.flatten())

    # add vertex colors
    if color.shape[0] == len(mesh.vertices):
        colorLayer = mesh.vertex_colors.new(name="Col")
        colorData = colorLayer.data
        loopColors = color[loopVertexIndices]

        colorLayer.data.foreach_set("color", loopColors.flatten())
    
    
    if (
        weights.shape[0] == len(mesh.vertices)
        and boneIDs.shape[0] == len(mesh.vertices)
        and sklObj
    ):
        # Add Armature modifier
        armatureMod = obj.modifiers.new(name="Armature", type='ARMATURE')
        armatureMod.object = sklObj

        # Ensure proper types and shapes
        weights = np.asarray(weights, dtype=np.float32)
        boneIDs = np.asarray(boneIDs, dtype=np.int32)
        if weights.shape[1] != boneIDs.shape[1]:
            raise ValueError("weights and boneIDs must have the same number of columns")

        # Collect only the bone indices actually used by this model's bone maps
        usedBoneIndices = sorted({int(idx) for bm in msbModel.boneMaps for idx in bm.boneIndices})
        boneIndexToVG = {skelIdx: vgIdx for vgIdx, skelIdx in enumerate(usedBoneIndices)}
        vgList = [obj.vertex_groups.new(name=msbSkl.bones[skelIdx].name) for skelIdx in usedBoneIndices]

        # Iterate over all vertices safely
        numVerts = len(mesh.vertices)
        numWeights = weights.shape[1]

        for v in range(numVerts):
            for i in range(numWeights):
                w = float(weights[v, i])
                if w <= 0.0:
                    continue

                skelIndex = int(boneIDs[v, i])
                vgIdx = boneIndexToVG.get(skelIndex)
                if vgIdx is None:
                    continue

                vgList[vgIdx].add([v], w, 'ADD')
    
    
    return obj

def importMIB(filepath):
    with open(filepath, "rb") as f:
        br = BinaryReader(f.read())
        mib: MIB = br.read_struct(MIB)
        
        saved_textures = set()

        for i, texture in enumerate(mib.textures):
            dds_data = texture.convertToDDS()
            
            # temp output path
            temp_dir = tempfile.gettempdir()
            if texture.name in saved_textures:
                output_path = os.path.join(temp_dir, f"{texture.name}_{i}.dds")
            else:
                output_path = os.path.join(temp_dir, f"{texture.name}.dds")
                saved_textures.add(texture.name)
            
            
            # Write DDS file and pack into Blender
            with open(output_path, "wb") as outFile:
                outFile.write(dds_data)
            bpy.data.images.load(output_path)
            saved_textures.add(texture.name)
            print(f"Imported texture: {texture.name} from MIB file: {filepath}")


def menu_func_import(self, context):
    self.layout.operator(MSB_IMPORTER_OT_IMPORT.bl_idname,
                        text='MSB Model Importer (.msb)',
                        icon='IMPORT')

def register():
    bpy.utils.register_class(MSB_IMPORTER_OT_IMPORT)
    bpy.utils.register_class(MSB_FH_import)
    bpy.utils.register_class(MIB_IMPORTER_OT_IMPORT)
    bpy.utils.register_class(MIB_FH_import)
    bpy.utils.register_class(DropMIBOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
def unregister():
    bpy.utils.unregister_class(MSB_IMPORTER_OT_IMPORT)
    bpy.utils.unregister_class(MSB_FH_import)
    bpy.utils.unregister_class(MIB_IMPORTER_OT_IMPORT)
    bpy.utils.unregister_class(MIB_FH_import)
    bpy.utils.unregister_class(DropMIBOperator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)