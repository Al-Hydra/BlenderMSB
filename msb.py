import os
import sys

from .utils.PyBinaryReader.binary_reader import *

import numpy as np


class MSB(BrStruct):
    def __init__(self):
        self.models = []
        self.skeleton = None
        self.materials = []
    
    def __br_read__(self, br):
        self.magic = br.read_bytes(4)
        self.version = br.read_uint32()
        self.flag = br.read_uint32()
        self.unk = br.read_uint16()
        self.contentCount = br.read_uint16()
        self.contentOffsets = br.read_uint32(self.contentCount)
        
        self.models = []
        self.materials = []
        for offset in self.contentOffsets:
            br.seek(offset)
            empty = br.read_uint32()
            dataSize = br.read_uint32()
            dataOffset = br.read_uint32()
            dataType = br.read_uint16()
            count = br.read_uint16()
            br.seek(offset + dataOffset)
            
            dataBuffer = br.read_bytes(dataSize)
            br_data = BinaryReader(dataBuffer)
            
            if dataType == 0:
                model = br_data.read_struct(msbModel)
                self.models.append(model)
            elif dataType == 3:
                material = br_data.read_struct(msbMaterial)
                self.materials.append(material)
            elif dataType == 4:
                self.skeleton = br_data.read_struct(msbSkeleton, None, count)
            else:
                # Skip unknown content types
                pass


class msbSkeleton(BrStruct):
    def __init__(self):
        self.name = ""
        self.bones = []
    
    def __br_read__(self, br, count):
        
        for i in range(count):
            pos = br.pos()
            bone = msbBone()
            bone.index = i
            
            bone.matrix = br.read_float32(16)
            bone.vector1 = br.read_float32(4)  # unk1
            bone.vector2 = br.read_float32(4)  # unk2
            nameOffset = br.read_uint32()
            bone.name = br.read_str_at_offset(pos + nameOffset)
            bone.parentIndex = br.read_int16()
            unk1 = br.read_int16()
            bone.flag = br.read_int16()
            unk3 = br.read_int16()
            padding = br.read_uint32()
            self.bones.append(bone)
        
        

class msbBone:
    def __init__(self):
        self.name = ""
        self.parentIndex = None
        self.index = 0
        self.matrix = np.identity(4)
        self.vector1 = np.zeros(4)
        self.vector2 = np.zeros(4)

class msbMaterial(BrStruct):
    def __init__(self):
        self.name = ""
        self.textures = []
    
    def __br_read__(self, br):
        br.read_float32(22)  # unkFloats
        nameOffset = br.read_uint32()
        try:
            self.name = br.read_str_at_offset(nameOffset)
        except:
            self.name = br.read_str_at_offset(nameOffset, encoding='Shift-JIS')
        
        unk0 = br.read_uint32() 
        unk1 = br.read_uint16() 
        unk2 = br.read_uint16() 
        unk3 = br.read_uint16()
        count = br.read_uint16()
        
        br.read_uint64()  # unk4
        
        self.textures = []
        for _ in range(count):
            pos = br.pos()
            texture = {}
            texture['param1'] = br.read_float32(4)
            texture['param2'] = br.read_float32(3)
            textureNameOffset = br.read_uint32()
            texture['param3'] = br.read_float32(3)
            texture['unk3'] = br.read_uint32()
            
            try:
                texture['name'] = br.read_str_at_offset(textureNameOffset + pos)
            except:
                texture['name'] = br.read_str_at_offset(textureNameOffset + pos, encoding='Shift-JIS')

            self.textures.append(texture['name'])


class msbModel(BrStruct):
    def __init__(self):
        self.name = ""
        self.boundingBox = []
        self.vertexBuffers = []
        self.faceBuffers = []
    
    def __br_read__(self, br):
        pos = br.pos()
        self.boundingBox = br.read_float32(12)
        br.read_uint32()  # unk
        br.read_float32()  # unk1
        vertexBufferCount = br.read_uint16()
        faceBufferCount = br.read_uint16()
        dataStart = br.read_uint16()
        unk = br.read_uint16()
        self.parentBoneIndex = br.read_int16()  
        br.read_int16()  # unk5
        self.unk2 = br.read_uint32()  # a
        br.read_uint32()  # b
        br.read_uint32()  # c
        
        self.name = br.read_str()
        #print(f"Model name: {self.name}")
        # align name to 16 bytes
        if br.pos() % 16 != 0:
            br.seek(br.pos() + (16 - (br.pos() % 16)))
        
        self.vertexBuffers = br.read_struct(vertexBufferInfo, vertexBufferCount)
        self.faceBuffers = br.read_struct(faceBufferInfo, faceBufferCount)
        self.boneMaps = br.read_struct(boneMapInfo, vertexBufferCount)
        
        for bm in self.boneMaps:
            bm.boneIndices = br.read_uint16(bm.boneCount)
        
        buffersRead = 0
        for vb, bm in zip(self.vertexBuffers, self.boneMaps):
            br.seek(pos + dataStart + vb.vertexDataOffset + (buffersRead * 16))
            
            vertexDtype = vb.vertexDtype
            vertexCount = vb.vertexCount
            vb.vertices = np.frombuffer(br.read_bytes(vertexCount * np.dtype(vertexDtype).itemsize), dtype=vertexDtype)
            
            vb = self.processQuantizedData(vb)
            
            if 'boneIDs' in vb.vertices.dtype.names and len(bm.boneIndices) > 0:
                boneMap = np.array(bm.boneIndices, dtype='u4')
                vb.vertices['boneIDs'] = boneMap[vb.vertices['boneIDs']]
            
            buffersRead += 1
        
        for fb in self.faceBuffers:
            if fb.faceCount > 0:
                br.seek(pos + dataStart + fb.faceDataOffset + (buffersRead * 16))
                fb.faces = np.frombuffer(br.read_bytes(fb.faceCount * np.dtype('u2').itemsize), dtype='u2')
                buffersRead += 1
            else:
                # create faces using the vertex count
                vertexBuffer = self.vertexBuffers[fb.bufferIndex]
                vertexCount = vertexBuffer.vertexCount
                if fb.indexType == 0 and vertexCount % 3 == 0:
                    fb.faces = np.array(list(range(vertexCount)), dtype='u2')
                else:
                    fb.faces = np.array([], dtype='u2')
        
    def processQuantizedData(self, vb):
        def normalize(vectors):
            norms = np.linalg.norm(vectors[:, :3], axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return vectors[:, :3] / norms

        vertexDtype = vb.vertexDtype
        new_fields = []
        new_data = {}

        for name, dtype in vertexDtype:
            # Skip any alignment paddings
            if "padding" in name.lower():
                continue

            arr = vb.vertices[name]

            # --- Promote & decode quantized data ---
            if 'f2' in dtype:
                arr = arr.astype('f4')
            elif 'i1' in dtype:
                arr = arr.astype('f4') / 127.0
            elif 'u1' in dtype and name in ('color', 'weights'):
                arr = arr.astype('f4') / 255.0
            elif 'u1' in dtype and name.startswith('boneIDs'):
                arr = arr.astype('u4')
            elif 'i2' in dtype and name.startswith('uv'):
                arr = arr.astype('f4') / 8192.0
            elif 'i2' in dtype and name in ('normal', 'smoothedNormal'):
                arr = arr.astype('f4') * (1.0 / 32767.0)

            # --- Field-specific postprocess ---
            if name in ("normal", "tangent", "smoothedNormal"):
                if arr.shape[1] > 3:
                    arr = arr[:, :3]
                arr = normalize(arr)

            elif name in ("position", "morphPosition"):
                if arr.shape[1] > 3:
                    arr = arr[:, :3]

            elif name.startswith("uv"):
                if arr.shape[1] > 2:
                    arr = arr[:, :2]

            elif name == "weights":
                # ensure array is 2D
                if arr.ndim == 1:
                    arr = arr[:, None]
                # pad to 4 components if needed
                if arr.shape[1] < 4:
                    arr = np.hstack((arr, np.zeros((len(arr), 4 - arr.shape[1]), dtype='f4')))
                elif arr.shape[1] > 4:
                    arr = arr[:, :4]

            elif name.startswith('boneIDs'):
                if arr.ndim == 1:
                    arr = arr[:, None]
                if arr.shape[1] < 4:
                    arr = np.hstack((arr, np.zeros((len(arr), 4 - arr.shape[1]), dtype='u4')))
                elif arr.shape[1] > 4:
                    arr = arr[:, :4]

            new_data[name] = arr
            if name.startswith('boneIDs'):
                new_fields.append((name, '4u4'))
            else:
                new_fields.append((name, f"{arr.shape[1]}f4"))

        # --- Build new structured vertex buffer ---
        new_dtype = np.dtype(new_fields)
        new_vertices = np.empty(len(vb.vertices), dtype=new_dtype)
        for name, arr in new_data.items():
            new_vertices[name] = arr

        vb.vertices = new_vertices
        vb.vertexDtype = new_fields
        return vb



class vertexBufferInfo(BrStruct):
    def __init__(self):
        self.vertices = []
    
    def __br_read__(self, br):
        self.vertexFlags = br.read_uint32()
        self.hasUVs = br.read_int8()
        self.uvFlag = br.read_uint8()
        self.quantizeFlag = br.read_uint8()
        self.skinningFlag = br.read_uint8()
        
        self.vertexCount = br.read_uint32()
        self.vertexDataOffset = br.read_int32()
        
        # create a structure to hold vertices
        self.vertexDtype = []
        
        #position
        if self.vertexFlags & 1:
            if self.quantizeFlag & 4:
                self.vertexDtype.extend([('position', '4f2')])
                
                if self.vertexFlags & 4:
                    self.vertexDtype.extend([('morphPosition', '4f2')])
                
            else:
                self.vertexDtype.extend([('position', '3f4')])
                
                if self.vertexFlags & 4:
                    self.vertexDtype.extend([('morphPosition', '3f4')])
        
        
        elif self.vertexFlags & 2:
            if self.quantizeFlag & 4:
                self.vertexDtype.extend([('position', '4f2')])
                
                if self.vertexFlags & 4:
                    self.vertexDtype.extend([('morphPosition', '3f2')])
            
            else:
                self.vertexDtype.extend([('position', '4f4')])
                
        
                if self.vertexFlags & 4:
                    self.vertexDtype.extend([('morphPosition', '3f4')])
            
            
        #normals
        if self.vertexFlags & 1:
            
            if (self.quantizeFlag & 16):
                
                self.vertexDtype.extend([('normal', '4i1')])
            elif (self.vertexFlags & 16):
                self.vertexDtype.extend([('normal', '3f4')])
            
        
        elif self.vertexFlags & 2:
            if self.quantizeFlag & 16:
                self.vertexDtype.extend([('normal', '3i1')])
            elif self.vertexFlags & 16:
                self.vertexDtype.extend([('normal', '3f4')])

        # could be tangents
        if self.vertexFlags & 256:
            self.vertexDtype.extend([('unkAtt1', '4i1')])

        # unk
        if self.vertexFlags & 1024:
            self.vertexDtype.extend([('unkAtt2', '4i1')])

        # UVs
        if self.hasUVs:
            if self.quantizeFlag & 32:
                for i in range(self.uvFlag + 1):
                    self.vertexDtype.extend([(f'uv{i}', '2f2')])
            else:
                for i in range(self.uvFlag + 1):
                    self.vertexDtype.extend([(f'uv{i}', '2f4')])
        
        # vertex color always present
        self.vertexDtype.extend([('color', '4u1')])

        if self.skinningFlag & 0x0F:
            
            if self.quantizeFlag & 128:
                if self.skinningFlag & 1:
                    # 1 weight
                    self.vertexDtype.extend([('weights', '1u1')])
                    if self.vertexFlags & 1:
                        self.vertexDtype.extend([('weightPadding', '3u1')])
                    self.vertexDtype.extend([('boneIDs', '1u1')])
                    #self.vertexDtype.extend([('boneIDPadding', '3u1')])
                elif self.skinningFlag & 2:
                    # 2 weights
                    self.vertexDtype.extend([('weights', '2u1')])
                    if self.vertexFlags & 1:
                        self.vertexDtype.extend([('weightPadding', '2u1')])
                    self.vertexDtype.extend([('boneIDs', '2u1')])
                    #self.vertexDtype.extend([('boneIDPadding', '2u1')])

                elif self.skinningFlag & 4:
                    # 3 weights
                    self.vertexDtype.extend([('weights', '3u1')])
                    if self.vertexFlags & 1:
                        self.vertexDtype.extend([('weightPadding', '1u1')])

                    self.vertexDtype.extend([('boneIDs', '3u1')])
                    #self.vertexDtype.extend([('boneIDPadding', '1u1')])
                elif self.skinningFlag & 8:
                    # 4 weights
                    self.vertexDtype.extend([('weights', '4u1')])
                    self.vertexDtype.extend([('boneIDs', '4u1')])
            
            else:
                
                if self.skinningFlag & 1:
                    # 1 weight
                    self.vertexDtype.extend([('weights', '1f4')])
                    self.vertexDtype.extend([('boneIDs', '1u1')])
                
                elif self.skinningFlag & 2:
                    # 2 weights
                    self.vertexDtype.extend([('weights', '2f4')])
                    self.vertexDtype.extend([('boneIDs', '2u1')])
                elif self.skinningFlag & 4:
                    # 3 weights
                    self.vertexDtype.extend([('weights', '3f4')])
                    self.vertexDtype.extend([('boneIDs', '3u1')])
                elif self.skinningFlag & 8:
                    # 4 weights
                    self.vertexDtype.extend([('weights', '4f4')])
                    self.vertexDtype.extend([('boneIDs', '4u1')])
                
        
        # check if the stride is a multiple of 4 bytes, if not add padding
        stride = sum(np.dtype(dtype).itemsize for _, dtype in self.vertexDtype)
        if stride % 4 != 0:
            paddingSize = 4 - (stride % 4)
            self.vertexDtype.append((f'padding{len(self.vertexDtype)}', f'{paddingSize}u1'))
        
        #print(f"Vertex Buffer Dtype: {self.vertexDtype}")


class faceBufferInfo(BrStruct):
    def __init__(self):
        self.faceCount = 0
        self.faceDataOffset = 0
    
    def __br_read__(self, br):
        self.faceCount = br.read_uint32()
        self.faceDataOffset = br.read_int32()
        self.bufferIndex = br.read_uint16()
        self.materialIndex = br.read_uint16()
        self.indexType = br.read_uint32()


class boneMapInfo(BrStruct):
    def __init__(self):
        self.boneIndices = []
    
    def __br_read__(self, br):
        self.dataOffset = br.read_uint32()
        self.boneCount = br.read_uint32()

if __name__ == "__main__":
    
    # game directory
    game_dir = r""
    
    # test msb files
    file_counter = 0
    failed_files = []
    for root, dirs, files in os.walk(game_dir):
        for file in files:
            if file.endswith(".msb"):
                file_path = os.path.join(root, file)
                print(f"Testing {file_path}...")
                file_counter += 1
                try:
                    with open(file_path, "rb") as f:
                        msb = MSB()
                        msb.__br_read__(BinaryReader(f.read()))
                except Exception as e:
                    print(f"Failed to read {file_path}: {e}")
                    failed_files.append(file_path)
    
    
    if failed_files:
        print("\nFailed to read the following files:")
        for file in failed_files:
            print(file)
    print(f"Tested {file_counter} files with {len(failed_files)} failures.")