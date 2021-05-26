# DensoToXDF
Script to pull data from Denso SuperH ECU map lookup table and autogenerate a TunerPro definiton file

### Introduction

Denso SH-based ECUs contain a map lookup table, which specifies most of the maps used by the ECU logic (such as ignition or fuel parameters as a function of various other data).
The lookup table contains the dimensions of the map, the hexadecimal offsets for the axis and map data, and their data format (usually uint8 or uint16 in this case).
This program pulls that information and writes a TunerPro definition file based on the data, which one can use to further examine, name and adjust the maps in TunerPro.
By default, the maps will be named as follows: **"(2D or 3D) map x(x-axis length)y(y-axis length) at (z-axis data offset)"**. This way the maps can be ordered
based on the offset of the actual map data, which usually gives hints about their application.

The list generated by the program is comprehensive, but not exhaustive. The reason being is that some "maps" (and switch-type parameters, for example) are stored outside the map
region or are not specified in the lookup table. Finding these will require some reverse engineering with your favorite disassembler.

### How to use

Run xdfgenerator.py in Python and specify the file name and start offset of the map lookup table. This address varies from model to model,
but 0x28000 and 0x2C000 are some of the most common ones. If needed, use a hex editor to find your address, it should be obvious (preceded by lots of FF).
