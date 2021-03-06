import os

import psutil
from pyffi.formats.nif import NifFormat
import mathutils

from singleton import NifData, NifOp
import struct
import operator
import numpy as np
from colorama import Fore, Back, Style
from wand import image
from pygltflib import ImageFormat, BufferFormat, GLTF2
from gltf_builder import GLTFFile
import argparse
import subprocess as sp
import math

parser = argparse.ArgumentParser(description='Process a single NIF file.')
parser.add_argument('Path',
                       metavar='path',
                       type=str,
                       help='the path to the nif file')

parser.add_argument('TexRoot',
                       metavar='texroot',
                       type=str,
                       help='the directory at which texture searching will begin')

parser.add_argument('InFolder',
                       metavar='infolder',
                       type=str,
                       help='the directory containing the input structure')

parser.add_argument('OutFolder',
                       metavar='outfolder',
                       type=str,
                       help='the directory containing the output structure')

parser.add_argument("-u","--unrealmode",action="store_true",help="Pipes the alpha state into the metalness parameter of the material as many Unreal GLTF importers dont support different types of transparency")

args = parser.parse_args()
print(args)

class NIFFile:
    filename = ""
    gltf = None
    gltf_path = ""
    bin_path = ""
    texture_root = ""
    gltf_index = 0
    gltf_indices = []
    gltf_buffers = []
    gltf_offset = 0
    gltf_acoffset = 0

    transform_offset = mathutils.Matrix()

    gltf_trilength = 0
    gltf_vertlength = 0

    in_folder = ""
    out_folder = ""

    def save_gltf(self):
        self.gltf.save()
        #glb = GLTF2().load(self.gltf_path)
        #glb.convert_images(ImageFormat.DATAURI)  # convert images to data URIs.
        #glb.convert_buffers(BufferFormat.BINARYBLOB)  # convert buffers to GLB blob
        #glb.save_binary(self.gltf_path.replace(".gltf", ".glb"))
        print(Back.GREEN + Fore.BLACK + "FILE PROCESSED: " + os.path.abspath(self.gltf_path))

    def set_parents(self, n_block):
        """Set the parent block recursively through the tree, to allow
        crawling back as needed."""
        if isinstance(n_block, NifFormat.NiNode):
            # list of non-null children
            children = [child for child in n_block.children if child]
            for child in children:
                child._parent = n_block
                self.set_parents(child)

    def normalize(self, v):
        norm = np.linalg.norm(v, ord=1)
        if norm == 0:
            norm = np.finfo(v.dtype).eps
            norm = np.finfo(v.dtype).eps
        return v / norm

    def read_geometry_object(self, n_block, parent):
        ni_name = n_block.name.decode()

        # shortcut for mesh geometry data
        n_tri_data = n_block.data

        if n_tri_data and ni_name != "":
            print(Fore.YELLOW + "Importing mesh data for geometry " + Fore.GREEN + f"'{ni_name}'")

            # create mesh data
            #transform_matrix = mathutils.Matrix(n_block.get_transform().as_list()).transposed()
            transform_matrix = mathutils.Matrix(n_block.get_transform(parent).as_list()).transposed()
            print("Before")
            print(transform_matrix)

            transform_matrix @= self.transform_offset

            print("After")
            print(transform_matrix)
            print(self.transform_offset)

            print(transform_matrix)

            vertices = n_tri_data.vertices

            normals = n_tri_data.normals
            tangents = n_tri_data.tangents
            uvs = n_tri_data.uv_sets
            vertex_colors = n_tri_data.vertex_colors

            # vertex_colors = np.array([(color.r, color.g, color.b, 1.0) for color in vertex_colors], dtype=tuple)

            try:
                uvs = np.array([uv.as_list() for uv in uvs.get_item(0)])
            except:
                print(Fore.YELLOW + "No UV data present" + Fore.WHITE)

            print(str(len(vertices)) + " before")
            # buffer vertices
            np_verts = []
            for idx, vertex in enumerate(vertices):
                np_verts.append(vertex.as_tuple())
            #while (length % 3 != 0 or length % 4 != 0):
            while (len(np_verts) % 12 != 0):
                np_verts.append(np_verts[len(np_verts) - 1])
            #while length % 3 != 0:
            #    np_verts.append(np_verts[0])
            np_verts = np.array(np_verts, dtype=tuple)
            vertices = np_verts
            print(str(len(np_verts)) + " after")

            # buffer tris
            print(str(len(n_tri_data.get_triangles())) + " before")
            np_tris = []
            for idx, tri in enumerate(n_tri_data.get_triangles()):
                np_tris.append(tri[0])
                np_tris.append(tri[1])
                np_tris.append(tri[2])
            #while length < len(vertices):
            #    np_tris.append(np_tris[0])
            #    length += 1
            #while (length % 3 != 0 or length % 4 != 0):
            while (len(np_tris) % 12 != 0):
                np_tris.append(0)
            np_tris = np.array(np_tris, dtype=np.uint16)
            triangles = np_tris
            print(str(len(np_tris)) + " after")

            # buffer normals
            np_normals = []
            for idx, norm in enumerate(normals):
                v = np.array([norm.x, norm.y, norm.z])
                #sum = 0
                #for f in v:
                #    sum += f * f
                #if abs(math.sqrt(sum) - 1) <= 0.1:
                #    vu = np.array([0.0, 0.0, 1.0])
                #else:
                vu = v

                np_normals.append(tuple((vu[0], vu[1], vu[2])))
            while len(np_normals) < len(vertices):
                np_normals.append(np_normals[0])
            np_normals = np.array(np_normals, dtype=tuple)
            normals = np_normals

            # buffer tangents
            np_tangents = []
            for idx, tangent in enumerate(tangents):
                np_tangents.append(tangent.as_tuple() + (1.0,))
            while len(np_tangents) < len(vertices):
                np_tangents.append(np_tangents[0])
            np_tangents = np.array(np_tangents, dtype=tuple)
            tangents = np_tangents

            # buffer uvs
            np_uvs = []
            for idx, uv in enumerate(uvs):
                np_uvs.append(uv)
            while len(np_uvs) < len(vertices):
                np_uvs.append(np_uvs[0])
            #np_uvs = np.array(np_uvs, dtype=tuple)
            uvs = np_uvs

            # buffer vertex colors
            np_vertcolors = []
            length = 0
            for idx, col in enumerate(vertex_colors):
                length += 1
                np_vertcolors.append((col.r, col.g, col.b, 1.0))
            while len(np_vertcolors) < len(vertices):
                np_vertcolors.append([1.0, 1.0, 1.0, 1.0])
            np_vertcolors = np.array(np_vertcolors, dtype=tuple)
            vertex_colors = np_vertcolors

            # assemble into a gltf structure
            vertex_data = np.ones(len(vertices), dtype=[
                ("position", np.float32, 3),
                ("normal", np.float32, 3),
                ("tangent", np.float32, 4),
                ("texCoord0", np.float32, 2),
                ("color", np.float32, 4),
            ])


            # get textures for object
            textures = []
            imagemagicks = []
            try:
                for texture in n_block.bs_properties[0].texture_set.textures:
                    if texture.decode("utf-8") != "" and texture is not None:
                        texture_file = os.path.normpath(os.path.join(self.texture_root, texture.decode("utf-8")))
                        out_texture_file = os.path.join(os.path.abspath(self.out_folder), os.path.relpath(texture_file.replace(".dds", ".png").lower(), self.in_folder))


                        # convert and copy textures to PNGs by the GLTF file
                        # image = pyvips.Image.new_from_file(texture_file, access='sequential')
                        # image.write_to_file(out_texture_file)
                        # im = Image.open(texture_file)
                        # im.save(out_texture_file, "PNG")
                        #startupinfo = sp.STARTUPINFO()
                        #startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
                        #imagemagick = sp.Popen(['imagemagick/convert.exe', texture_file, out_texture_file], startupinfo=startupinfo).pid
                        #imagemagick = sp.Popen(['vips/vips.exe', "affine", texture_file, out_texture_file, ' 1 0 0 1'], startupinfo=startupinfo).pid
                        #imagemagicks.append(imagemagick)
                        #with image.Image(filename=texture_file) as img:
                        #    img.compression = "no"
                        #    img.save(filename=out_texture_file)

                        #out_path = os.path.relpath(os.path.abspath(out_texture_file.replace("textures\\", "")), os.path.abspath(self.gltf_path))
                        #textures.append(out_path[6:len(out_path)].replace("\\", "/"))
                        textures.append(out_texture_file.replace("\\", "/"))
                print(textures)
                #while len(imagemagicks) > 0:
                #    for p in imagemagicks:
                #        if not psutil.pid_exists(p):
                #            print(Fore.GREEN + "PID: [" + str(p) + "] Finished texture job")
                #            imagemagicks.remove(p)
            except:
                print(Fore.YELLOW + "No texture data present" + Fore.WHITE)

            # alpha flags
            alpha_threshold = 128
            alpha_blend = False
            alpha_test = False
            glossiness = 1.0
            if n_block.bs_properties[0] is not None:
                if hasattr(n_block.bs_properties[0], 'glossiness'):
                    glossiness = n_block.bs_properties[0].glossiness / 255
                    print(Fore.WHITE + "Setting glossiness (roughness) to " + str(glossiness))
            if n_block.bs_properties[1] is not None:
                alpha_threshold = n_block.bs_properties[1].threshold / 255
                print("Setting alpha threshold to " + str(alpha_threshold))

                flags = n_block.bs_properties[1].flags
                if flags & 1:
                    alpha_blend = True
                    print("Enabling alpha blend for material")
                if flags & (1 << 9):
                    alpha_test = True
                    print("Enabling alpha testing for material")
            else:
                print("Material doesn't have alpha, disabling")
                alpha_test = False
                alpha_blend = False

            print("printing lengths:")
            print(len(vertices))
            print(len(triangles))
            print(len(normals))
            print(len(tangents))
            print(len(uvs))
            print(len(vertex_colors))

            #try:
            vertex_data["position"] = vertices
            vertex_data["normal"] = normals
            vertex_data["tangent"] = tangents
            vertex_data["texCoord0"] = uvs
            vertex_data["color"] = vertex_colors
            #except:
            #    print("Could not load one or more attributes")

            for idx, normal in enumerate(vertex_data['normal']):
                vu = np.array([0.0, 0.0, 1.0])
                sum = 0
                for f in normal:
                    sum += f * f
                if not abs(math.sqrt(sum) - 1) <= 0.1:
                    vu = normal
                vertex_data['normal'][idx] = vu

            self.gltf.numpy_to_gltf(vertex_data,
                                    triangles,
                                    transform_matrix,
                                    textures,
                                    alpha_threshold,
                                    alpha_blend,
                                    alpha_test,
                                    glossiness,
                                    ni_name, args.unrealmode)
        else:
            print(Fore.YELLOW + f"Skipping, no shape data found {ni_name}")

    def read_branch(self, n_block, parent):

        print(f"Importing data for block '{n_block.name.decode()}'")

        # recursive loop through nif tree
        if not n_block:
            return None

        if isinstance(n_block, NifFormat.NiTriBasedGeom):
            return self.read_geometry_object(n_block, parent)
        else:
            self.transform_offset @= mathutils.Matrix(n_block.get_transform().as_list()).transposed()

        # find children
        b_children = []
        if hasattr(n_block, 'children'):
            n_children = [child for child in n_block.children]
            for n_child in n_children:
                self.read_branch(n_child, n_block)
            print("Resetting working transform")
            self.transform_offset = mathutils.Matrix()

    def read_root(self, root_block):

        # divinity 2: handle CStreamableAssetData
        if isinstance(root_block, NifFormat.CStreamableAssetData):
            root_block = root_block.root

        # sets the root block parent to None, so that when crawling back the script won't barf
        root_block._parent = None

        # set the block parent through the tree, to ensure I can always move backward
        self.set_parents(root_block)

        # import this root block
        print(
            Back.BLUE + Fore.BLACK + Style.BRIGHT + f"PROCESSING ROOT BLOCK: {root_block.get_global_display()}" + Style.RESET_ALL)
        self.filename = root_block.get_global_display().replace(".nif", "")
        self.gltf_path = os.path.normpath(os.path.join(self.gltf_path, self.filename, self.filename + ".gltf"))
        self.bin_path = os.path.abspath(os.path.normpath(os.path.join(self.bin_path, self.filename, self.filename + ".bin"))).replace("\\", "/")

        # generate output folder structure
        if not os.path.exists(os.path.dirname(self.gltf_path)):
            os.makedirs(os.path.dirname(self.gltf_path))

        self.gltf = GLTFFile(root_block.get_global_display(), self.gltf_path, self.bin_path)

        if isinstance(root_block, (NifFormat.NiNode, NifFormat.NiTriBasedGeom)):
            root_block.__annotations__ = "root_of_file"
            self.read_branch(root_block, root_block)
        elif isinstance(root_block, NifFormat.NiCamera):
            print('Skipped NiCamera root')

        elif isinstance(root_block, NifFormat.NiPhysXProp):
            print('Skipped NiPhysXProp root')

        else:
            print(f"Skipped unsupported root block type '{root_block.__class__}' (corrupted nif?).")

    def __init__(self, texture_root, filepath, in_folder, out_folder):
        data = NifFormat.Data()
        with open(filepath, "rb") as nif_stream:
            print("Reading %s" % os.path.basename(filepath))
            data.read(nif_stream)

        base_path = os.path.join(out_folder, os.path.relpath(os.path.dirname(filepath), in_folder))
        self.gltf_path = base_path
        self.bin_path = base_path
        self.in_folder = in_folder
        self.out_folder = out_folder

        self.texture_root = texture_root
        for block in data.roots:
            root = block
            self.transform_offset.translation += mathutils.Matrix(root.get_transform().as_list()).transposed().translation
            self.read_root(root)

niffile = NIFFile(args.TexRoot, args.Path, args.InFolder, args.OutFolder)
niffile.save_gltf()