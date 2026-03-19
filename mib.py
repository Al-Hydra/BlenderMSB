from .utils.PyBinaryReader.binary_reader import *
import zlib
class MIB(BrStruct):
    def __init__(self):
        self.textures = []
    
    def __br_read__(self, br):
        self.magic = br.read_bytes(4)
        self.version = br.read_uint32()
        self.unk = br.read_uint32()
        self.unk2 = br.read_uint16()
        self.count = br.read_uint16()
        self.offsets = br.read_uint32(self.count)
        
        self.textures = []
        
        for offset in self.offsets:
            br.seek(offset)
            texture = br.read_struct(mibTexture)
            self.textures.append(texture)

pixelFormatDict = {
    8: "DXT1",
    9: "DXT3",
    10: "DXT5",
}

class mibTexture(BrStruct):
    def __init__(self):
        self.name = ""
        self.width = 0
        self.height = 0
        self.pixelFormat = 0
        self.textureData = []
    
    def __br_read__(self, br):
        pos = br.pos()
        flag = br.read_uint32()
        if flag == 0:
            self.textureSize = br.read_uint32()
            self.textureDataOffset = br.read_uint32()
        
        
        self.unk5 = br.read_uint16()
        self.unk6 = br.read_uint16()
        self.pixelFormat = br.read_uint32()
        self.width = br.read_uint16()
        self.height = br.read_uint16()
        self.unk8 = br.read_uint16()
        self.unk9 = br.read_uint16()
        self.unk10 = br.read_uint32()
        
        self.textureSize = br.read_uint32()
        self.compressionFlag = br.read_uint32()
        try:
            namePos = br.pos()
            self.name = br.read_str()
        except:
            br.seek(namePos, 0)
            self.name = br.read_str(encoding = 'Shift-JIS')

        if flag != 0:
            self.padding = br.read_uint64()
        else:
            br.seek(pos + self.textureDataOffset, 0)

        self.textureData = br.read_bytes(self.textureSize)
        if self.compressionFlag == 131072:
            self.textureData = zlib.decompress(self.textureData)
    
    def convertToDDS(self):
        ddsHeader = bytearray()
        ddsHeader.extend(b'DDS ')
        ddsHeader.extend((124).to_bytes(4, 'little'))  # size
        ddsHeader.extend((0x0002100F).to_bytes(4, 'little'))  # flags
        ddsHeader.extend((self.height).to_bytes(4, 'little'))  # height
        ddsHeader.extend((self.width).to_bytes(4, 'little'))  # width
        ddsHeader.extend((0).to_bytes(4, 'little'))  # pitchOrLinearSize
        ddsHeader.extend((0).to_bytes(4, 'little'))  # depth
        ddsHeader.extend((1).to_bytes(4, 'little'))  # mipMapCount
        ddsHeader.extend((0).to_bytes(44, 'little'))  # reserved1[11]
        
        # Pixel Format
        ddsHeader.extend((32).to_bytes(4, 'little'))  # size
        ddsHeader.extend((0x00000004).to_bytes(4, 'little'))  # flags
        fourCC = pixelFormatDict.get(self.pixelFormat, "DXT1")
        ddsHeader.extend(fourCC.encode('utf-8'))  # fourCC
        ddsHeader.extend((0).to_bytes(4, 'little'))  # RGBBitCount
        ddsHeader.extend((0).to_bytes(4, 'little'))  # RBitMask
        ddsHeader.extend((0).to_bytes(4, 'little'))  # GBitMask
        ddsHeader.extend((0).to_bytes(4, 'little'))  # BBitMask
        ddsHeader.extend((0).to_bytes(4, 'little'))  # ABitMask
        
        ddsHeader.extend((0x00001000).to_bytes(4, 'little'))  # caps1
        ddsHeader.extend((0).to_bytes(4, 'little'))  # caps2
        ddsHeader.extend((0).to_bytes(4, 'little'))  # caps3
        ddsHeader.extend((0).to_bytes(4, 'little'))  # caps4
        ddsHeader.extend((0).to_bytes(4, 'little'))  # reserved2
        
        return bytes(ddsHeader) + self.textureData

if __name__ == "__main__":
    path = r""
    output = r""
    
    with open(path, "rb") as f:
        br = BinaryReader(f.read())
        mib = br.read_struct(MIB)

        for i, texture in enumerate(mib.textures):
            ddsData = texture.convertToDDS()
            with open(f"{output}/{i}_{texture.name}.dds", "wb") as outFile:
                outFile.write(ddsData)