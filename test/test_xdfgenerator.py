import pytest
import struct
from pathlib import Path
from unittest import mock
from datetime import datetime
from xdfgenerator import *

# Sample valid 2D and 3D mapinfo structs (from Suzuki 32920-21H10 ECU)
@pytest.fixture
def valid_2d_mapinfo():
    return b'\x09\x1d\xff\xff\x00\x06\x07\x04\x00\x06\x08\xa6\x00\x00\x00\x00'

@pytest.fixture
def valid_3d_mapinfo():
    return b'\x29\x06\x19\xff\x00\x08\x00\x00\x00\x08\x00\x0c\x00\x08\x03\x48\x00\x00\x00\x00'
    
def test_mapinfo_from_bytes_2d(valid_2d_mapinfo):
    mapinfo = MapInfo.from_bytes(valid_2d_mapinfo)
    assert mapinfo._type == '2d'
    assert mapinfo._id == 0x9
    assert mapinfo.x_len == 29
    assert mapinfo.x_addr == 0x60704
    assert mapinfo.y_addr == None
    assert mapinfo.z_addr == 0x608a6
    assert mapinfo.x_format == 16
    assert mapinfo.z_format == 8

def test_mapinfo_from_bytes_3d(valid_3d_mapinfo):
    mapinfo = MapInfo.from_bytes(valid_3d_mapinfo)
    assert mapinfo._type == '3d'
    assert mapinfo._id == 0x29
    assert mapinfo.x_len == 6
    assert mapinfo.y_len == 25
    assert mapinfo.x_addr == 0x80000
    assert mapinfo.y_addr == 0x8000c
    assert mapinfo.z_addr == 0x80348
    assert mapinfo.x_format == 16
    assert mapinfo.z_format == 8


def test_get_map_type():
    assert MapInfo.get_map_type(0x09) == '2d'
    assert MapInfo.get_map_type(0x29) == '3d'
    with pytest.raises(ValueError):
        MapInfo.get_map_type(0x2b)
    with pytest.raises(ValueError):
        MapInfo.get_map_type(0xff)

def test_validate_mapinfo_valid_2d(valid_2d_mapinfo):
    assert MapInfo.validate_map_info_format(valid_2d_mapinfo, 0x100000)
    
def test_validate_mapinfo_valid_3d(valid_3d_mapinfo):
    assert MapInfo.validate_map_info_format(valid_3d_mapinfo, 0x100000)

def test_validate_mapinfo_invalid_2d(valid_2d_mapinfo):
    invalid_data = valid_2d_mapinfo[:-1] + b'\x01'
    assert not MapInfo.validate_map_info_format(invalid_data, 0x100000)

def test_validate_mapinfo_invalid_3d(valid_3d_mapinfo):
    invalid_data = valid_3d_mapinfo[:-1] + b'\x01'
    assert not MapInfo.validate_map_info_format(invalid_data, 0x100000)

def test_lookup_table_offset_found():
    with open(Path(__file__).parent / '32920-41G00.bin', 'rb') as in_file:
        data = in_file.read()
    offset = MapInfo.find_lookup_table_offset(data)
    assert offset == 0x2C000
    
def test_get_mapinfo_size():
    assert MapInfo.get_map_info_size('2d') == 16
    assert MapInfo.get_map_info_size('3d') == 20

def test_get_element_sizes():
    # Bit 4 set → x=8, else x=16
    assert MapInfo.get_x_element_size(0b10000) == 8
    assert MapInfo.get_x_element_size(0b00000) == 16

    # Bit 2 set → y=8
    assert MapInfo.get_y_element_size(0b00100) == 8
    assert MapInfo.get_y_element_size(0b00000) == 16

    # Bit 0 set → z=8
    assert MapInfo.get_z_element_size(0b00001) == 8
    assert MapInfo.get_z_element_size(0b00000) == 16

def test_generate_xdf_matches_expected_output(tmp_path):
    # Arrange
    in_path = Path(__file__).parent / "32920-41G00.bin"
    expected_output_path = Path(__file__).parent / "32920-41G00.xdf"
    actual_output_path = tmp_path / "output.xdf"

    # Mock datetime to have a consistent timestamp
    fixed_datetime = datetime(2025, 4, 17, 23, 31, 6)
    with mock.patch("xdfgenerator.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_datetime
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        generate_xdf(str(in_path), str(actual_output_path), None)

    # Assert
    with open(actual_output_path, encoding='utf-16') as actual_file, \
         open(expected_output_path, encoding='utf-16') as expected_file:
        actual_content = actual_file.read()
        expected_content = expected_file.read()

    assert actual_content == expected_content, "Generated XDF does not match the expected output"
