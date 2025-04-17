from datetime import datetime
import argparse
import struct

# MapInfo represents an entry in the Denso map lookup table
class MapInfo():
    FORMAT_2D_MAPINFO = '>ccxxIIxxxx'
    FORMAT_3D_MAPINFO = '>cccxIIIxxxx'
    
    def __init__(self, _type: str, _id: int, x_len: int, y_len: int, x_addr: int, y_addr: int, z_addr: int):
        self._type = _type
        self._id = int.from_bytes(_id, byteorder='big')
        self.x_len = int.from_bytes(x_len, byteorder='big')
        self.y_len = int.from_bytes(y_len, byteorder='big') if y_len else None
        self.x_addr = x_addr
        self.y_addr = y_addr if y_len else None
        self.z_addr = z_addr
        self.x_format = self.get_x_element_size(self._id)
        self.z_format = self.get_z_element_size(self._id)
        if (_type == '3d'):
            self.y_format = self.get_y_element_size(self._id)
        else:
            self.y_format = None
    
    @classmethod
    def from_bytes(cls, data: bytes):
        if MapInfo.get_map_type(data[0]) == '3d':
            values = struct.unpack(MapInfo.FORMAT_3D_MAPINFO, data)
            return cls(_type='3d', _id=values[0], x_len=values[1], y_len=values[2], x_addr=values[3], y_addr=values[4], z_addr=values[5])
        else:
            values = struct.unpack(MapInfo.FORMAT_2D_MAPINFO, data)
            return cls(_type='2d', _id=values[0], x_len=values[1], y_len=None, x_addr=values[2], y_addr=None, z_addr=values[3])
        
    @classmethod
    def get_map_info_size(cls, map_type: str):
        if map_type == '3d':
            return struct.calcsize(cls.FORMAT_3D_MAPINFO)
        elif map_type == '2d':
            return struct.calcsize(cls.FORMAT_2D_MAPINFO)
        else:
            raise ValueError('unexpected map type')

    @staticmethod
    def get_map_type(_id: int) -> str:
        if _id > 0x2a:
            raise ValueError("unexpected id byte of map info")
        elif _id > 0xf:
            return '3d'
        else:
            return '2d'
        
    @staticmethod
    def get_x_element_size(_id: int) -> int:
        if (_id & (1 << 4)):
            return 8
        else:
            return 16
    
    @staticmethod
    def get_y_element_size(_id: int) -> int:
        if (_id & (1 << 2)):
            return 8
        else:
            return 16
    
    @staticmethod
    def get_z_element_size(_id: int) -> int:
        if (_id & 1):
            return 8
        else:
            return 16
        
    @staticmethod
    def validate_map_info_format(map_info_data: bytes, bin_size: int) -> bool:
        # try to check whether map_info_data is a valid MapInfo struct
        if map_info_data[3] not in [0, 0xff]: # padding byte, 0 or FF depending on version
            return False
        if not all(i == 0 for i in map_info_data[-4:]): # four zero-padding bytes at the end
            return False
        try:
            map_info = MapInfo.from_bytes(map_info_data)
            # must have plausible addresses
            if map_info.x_addr == 0 or map_info.x_addr >= bin_size:
                return False
            if map_info.y_addr:
                if map_info.y_addr == 0 or map_info.y_addr >= bin_size:
                    return False
            if map_info.z_addr == 0 or map_info.z_addr >= bin_size:
                return False
        except ValueError:
            return False
        return True
    
    @staticmethod
    def find_lookup_table_offset(data: bytes) -> int:
        # find the start offset of the map lookup table
        OFFSET_ALIGNMENT = 4    # to my best knowledge the structure is always 4-aligned
        VALID_N_THRESHOLD = 5   # at least n consecutive valid maps must be found to determine
                                # the start of the map lookup table
    
        position = 0
        candidate_offset: int = None
        valid_n = 0
        
        while position < len(data):
            try:
                map_type = MapInfo.get_map_type(data[position])
                map_info_size = MapInfo.get_map_info_size(map_type)
                map_info_bytes = data[position : position + map_info_size]
                if MapInfo.validate_map_info_format(map_info_bytes, len(data)):
                    if not candidate_offset:
                        candidate_offset = position
                    valid_n += 1
                    if valid_n >= VALID_N_THRESHOLD:
                        print(f"Found lookup table offset: {hex(candidate_offset)}")
                        return candidate_offset
                    # continue to where the next map is calculated to start
                    position += map_info_size
                    continue
            except ValueError:
                pass
            # the offset at "position" did not contain a valid MapInfo
            if candidate_offset:
                # go back to where we left off if it was not the offset we were looking for
                position = candidate_offset
                candidate_offset = None
            position += 1 * OFFSET_ALIGNMENT
            valid_n = 0
        raise ValueError("Cannot determine lookup table offset, please provide the --position argument.")

def generate_xdf(in_file: str, out_file: str, map_data_offset: int):
    # read the ECU bin into a buffer
    with open(in_file, 'rb') as input_file:
        input_bytes = input_file.read()
    
    if map_data_offset is not None: # user provided offset
        position = map_data_offset
    else: # attempt to find the offset
        position = MapInfo.find_lookup_table_offset(input_bytes)
        
    maps: list[MapInfo] = []
    
    # parse the binary data into MapInfo objects
    while position < len(input_bytes):
        map_info_id = input_bytes[position] # leading byte of the MapInfo struct
        try:
            map_type = MapInfo.get_map_type(map_info_id)
        except ValueError: # end of map lookup table
            break
        
        map_info_size = MapInfo.get_map_info_size(map_type)
        
        mapinfo_bytes = input_bytes[position : position + map_info_size]
        position += map_info_size
        
        map_info = MapInfo.from_bytes(mapinfo_bytes)
        maps.append(map_info)

    # create the XDF file from the MapInfo list
    with open(out_file, 'w', encoding='utf-16') as f_out:
        f_out.write(f"""<!-- Written on {str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))} by tientuk3 Denso SuperH XDF generator -->
<XDFFORMAT version="1.70">
    <XDFHEADER>
        <flags>0x1</flags>
        <description>Autogenerated by tientuk3 Denso SuperH XDF generator</description>
        <BASEOFFSET offset="0" subtract="0" />
        <DEFAULTS datasizeinbits="8" sigdigits="2" outputtype="1" signed="0" lsbfirst="0" float="0" />
        <REGION type="0xFFFFFFFF" startaddress="0x0" size="{hex(len(input_bytes))}" regionflags="0x0" name="Binary File" desc="This region describes the bin file edited by this XDF" />
    </XDFHEADER>""")
        
        unique_id = 0
        for map_info in maps:
            unique_id += 1
            if map_info._type == '3d':
                f_out.write(f"""
    <XDFTABLE uniqueid="{hex(unique_id)}" flags="0x0">
        <title>3D map x{map_info.x_len}y{map_info.y_len} at {hex(map_info.z_addr)}</title>
        <XDFAXIS id="x" uniqueid="0x0">
            <EMBEDDEDDATA mmedaddress="{hex(map_info.x_addr, )}" mmedelementsizebits="{map_info.x_format}" mmedcolcount="{map_info.x_len}" mmedmajorstridebits="{map_info.x_format}" mmedminorstridebits="0" />
            <indexcount>{map_info.x_len}</indexcount>
            <embedinfo type="1" />
            <datatype>0</datatype>
            <unittype>0</unittype>
            <DALINK index="0" />
            <MATH equation="X">
                <VAR id="X" />
            </MATH>
        </XDFAXIS>
        <XDFAXIS id="y" uniqueid="0x0">
            <EMBEDDEDDATA mmedaddress="{hex(map_info.y_addr)}" mmedelementsizebits="{map_info.y_format}" mmedcolcount="{map_info.y_len}" mmedmajorstridebits="{map_info.y_format}" mmedminorstridebits="0" />
            <indexcount>{map_info.y_len}</indexcount>
            <embedinfo type="1" />
            <datatype>0</datatype>
            <unittype>0</unittype>
            <DALINK index="0" />
            <MATH equation="X">
                <VAR id="X" />
            </MATH>
        </XDFAXIS>""")
                
            else: # 2d map
                f_out.write(f"""
    <XDFTABLE uniqueid="{hex(unique_id)}" flags="0x0">
        <title>2D map x{map_info.x_len} at {hex(map_info.z_addr)}</title>
        <XDFAXIS id="x" uniqueid="0x0">
        <EMBEDDEDDATA mmedaddress="{hex(map_info.x_addr)}" mmedelementsizebits="{map_info.x_format}" mmedcolcount="{map_info.x_len}" mmedmajorstridebits="{map_info.x_format}" mmedminorstridebits="0" />
        <indexcount>{map_info.x_len}</indexcount>
        <embedinfo _type="1" />
        <datatype>0</datatype>
        <unittype>0</unittype>
        <DALINK index="0" />
        <MATH equation="X">
            <VAR id="X" />
        </MATH>
        </XDFAXIS>""")
                
                f_out.write("""
        <XDFAXIS id="y" uniqueid="0x0">
        <EMBEDDEDDATA mmedelementsizebits="8" mmedmajorstridebits="-32" mmedminorstridebits="0" />
        <indexcount>1</indexcount>
        <embedinfo type="1" />
        <datatype>0</datatype>
        <unittype>0</unittype>
        <DALINK index="0" />
        <LABEL index="0" value="0.00" />
        <MATH equation="X">
            <VAR id="X" />
        </MATH>
        </XDFAXIS>
                            """)
            f_out.write(f"""
        <XDFAXIS id="z">
        <EMBEDDEDDATA mmedaddress="{hex(map_info.z_addr)}" mmedelementsizebits="{map_info.z_format}" mmedrowcount="{map_info.y_len}" mmedcolcount="{map_info.x_len}" mmedmajorstridebits="0" />
        <decimalpl>2</decimalpl>
        <min>0.000000</min>
        <max>5000.000000</max>
        <outputtype>2</outputtype>
        <MATH equation="X">
            <VAR id="X" />
        </MATH>
        </XDFAXIS>
    </XDFTABLE>""")
        f_out.write("""
</XDFFORMAT>""")

    print(f"{sum([1 for m in maps if m._type == '2d'])} 2D maps and {sum([1 for m in maps if m._type == '3d'])} 3D maps identified")
    print(f"Results written to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate TunerPro XDF definition file from Denso SuperH/M32R ECU binaries')
    parser.add_argument('--position', type=lambda val: int(val, 16),
                        help='''Hexadecimal offset of the start of the map data area. If this
                        argument is not provided, the program attempts to find it automatically.
                        ''')
    parser.add_argument('in_file', help='Input bin file path')
    parser.add_argument('out_file', help='Output XDF file path')
    args = parser.parse_args()
    
    generate_xdf(args.in_file, args.out_file, args.position)