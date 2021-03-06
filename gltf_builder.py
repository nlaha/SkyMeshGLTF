import os
import sys
import json

import numpy as np

from pygltf import gltf2 as gltf

ATTRIBUTE_BY_NAME = {
    "position": gltf.Attribute.POSITION,
    "normal": gltf.Attribute.NORMAL,
    "tangent": gltf.Attribute.TANGENT,
    "texCoord": gltf.Attribute.TEXCOORD,
    "texCoord0": gltf.Attribute.TEXCOORD_0,
    "texCoord1": gltf.Attribute.TEXCOORD_1,
    "color": gltf.Attribute.COLOR_0,
}

COMPONENT_TYPE_BY_DTYPE = {
    np.int8: gltf.ComponentType.BYTE,
    np.uint8: gltf.ComponentType.UNSIGNED_BYTE,
    np.int16: gltf.ComponentType.SHORT,
    np.uint16: gltf.ComponentType.UNSIGNED_SHORT,
    np.uint32: gltf.ComponentType.UNSIGNED_INT,
    np.float32: gltf.ComponentType.FLOAT,
}

ACCESSOR_TYPE_BY_SHAPE = {
    (): gltf.AccessorType.SCALAR,
    (1,): gltf.AccessorType.SCALAR,
    (2,): gltf.AccessorType.VEC2,
    (3,): gltf.AccessorType.VEC3,
    (4,): gltf.AccessorType.VEC4,
    (1, 1): gltf.AccessorType.SCALAR,
    (2, 2): gltf.AccessorType.MAT2,
    (3, 3): gltf.AccessorType.MAT3,
    (4, 4): gltf.AccessorType.MAT4,
}

class GLTFFile:
    document = None
    buffers = []
    gltf_path = ""
    bin_path = ""
    filename = ""

    offset = 0
    buffer = None

    def from_np_type(self, dtype, shape):
        accessorType = ACCESSOR_TYPE_BY_SHAPE.get(shape)
        componentType = COMPONENT_TYPE_BY_DTYPE.get(dtype.type)
        return accessorType, componentType


    def subtype(self, dtype):
        try:
            dtype, shape = dtype.subdtype
            return dtype, shape
        except TypeError:
            dtype, shape = dtype, ()
            return dtype, shape


    def generate_structured_array_accessors(self, data, buffer_views, offset=None, count=None, name=None):
        name = "{key}" if name is None else name
        count = len(data) if count is None else count
        result = {}
        for key, value in data.dtype.fields.items():
            dtype, delta = value
            dtype, shape = self.subtype(dtype)
            accessorType, componentType = self.from_np_type(dtype, shape)
            accessor = gltf.Accessor(buffer_views[key], offset, count, accessorType, componentType,
                                     name=name.format(key=key))
            attribute = ATTRIBUTE_BY_NAME.get(key)
            if attribute == gltf.Attribute.POSITION:
                accessor.max = np.amax(data[key], axis=0).tolist()
                accessor.min = np.amin(data[key], axis=0).tolist()
            result[attribute] = accessor
        return result


    def generate_array_accessor(self, data, buffer_view, offset=None, count=None, name=None):
        count = len(data) if count is None else count
        dtype, shape = data.dtype, data.shape
        accessorType, componentType = self.from_np_type(dtype, shape[1:])
        result = gltf.Accessor(buffer_view, offset, count, accessorType, componentType, name=name)
        return result


    def generate_structured_array_buffer_views(self, data, buffer, target, offset=None, name=None):
        name = "{key}" if name is None else name
        offset = 0 if offset is None else offset
        length = data.nbytes
        stride = data.itemsize
        result = {}
        for key, value in data.dtype.fields.items():
            dtype, delta = value
            dtype, shape = self.subtype(dtype)
            accessorType, componentType = self.from_np_type(dtype, shape)
            buffer_view = gltf.BufferView(buffer, offset + delta, length - delta, stride, target, name=name.format(key=key))
            result[key] = buffer_view
        return result


    def generate_array_buffer_view(self, data, buffer, target, offset=None, name=None):
        offset = 0 if offset is None else offset
        length = data.nbytes
        stride = None
        result = gltf.BufferView(buffer, offset, length, stride, target, name=name)
        return result


    def byteLength(self, buffers):
        return sum(map(lambda buffer: buffer.nbytes, buffers))

    def euler_to_quaternion(self, yaw, pitch, roll):

        qx = np.sin(roll / 2) * np.cos(pitch / 2) * np.cos(yaw / 2) - np.cos(roll / 2) * np.sin(pitch / 2) * np.sin(
            yaw / 2)
        qy = np.cos(roll / 2) * np.sin(pitch / 2) * np.cos(yaw / 2) + np.sin(roll / 2) * np.cos(pitch / 2) * np.sin(
            yaw / 2)
        qz = np.cos(roll / 2) * np.cos(pitch / 2) * np.sin(yaw / 2) - np.sin(roll / 2) * np.sin(pitch / 2) * np.cos(
            yaw / 2)
        qw = np.cos(roll / 2) * np.cos(pitch / 2) * np.cos(yaw / 2) + np.sin(roll / 2) * np.sin(pitch / 2) * np.sin(
            yaw / 2)

        return [qx, qy, qz, qw]

    def normalize_factor(self, in_val):
        if in_val > 1:
            return 1
        elif in_val < 0:
            return 0
        else:
            return in_val

    def numpy_to_gltf(self, vertex_data, index_data, transform_matrix, textures, alpha_threshold, alpha_blend, alpha_test, glossiness, mesh_name, unrealmode):
        mesh = gltf.Mesh([], name=mesh_name)
        mesh_material = gltf.Material()
        mesh_material.emissiveFactor = [3.0, 3.0, 3.0]
        alpha_enabled = 0.001

        if alpha_test:
            mesh_material.alphaMode = gltf.AlphaMode.MASK
            alpha_enabled = 1.0
            mesh_material.doubleSided = True
            mesh_material.alphaCutoff = alpha_threshold
        if alpha_blend:
            mesh_material.alphaMode = gltf.AlphaMode.BLEND
            alpha_enabled = 1.0
            mesh_material.doubleSided = True

        print(alpha_enabled)

        if len(textures) > 0:
            diffuse = gltf.Image(uri=textures[0])
            self.document.add_image(diffuse)
            diffuse_tex = gltf.Texture(source=diffuse, sampler=self.document.samplers[0])
            self.document.add_texture(diffuse_tex)
            diffuse_tex_info = gltf.TextureInfo(index=diffuse_tex)

            pbr = None

            if (unrealmode):
                pbr = gltf.PBRMetallicRoughness(baseColorTexture=diffuse_tex_info, roughnessFactor=self.normalize_factor(glossiness), metallicFactor=self.normalize_factor(alpha_enabled))
            else:
                pbr = gltf.PBRMetallicRoughness(baseColorTexture=diffuse_tex_info, roughnessFactor=self.normalize_factor(glossiness), metallicFactor=0.00001)
            mesh_material.pbrMetallicRoughness = pbr
        if len(textures) > 1:
            normmap = gltf.Image(uri=textures[1])
            self.document.add_image(normmap)
            normmap_tex = gltf.Texture(source=normmap, sampler=self.document.samplers[0])
            self.document.add_texture(normmap_tex)
            diffuse_tex_info = gltf.TextureInfo(index=normmap_tex)

            mesh_material.normalTexture = diffuse_tex_info
        if len(textures) > 2:
            emissive = gltf.Image(uri=textures[2])
            self.document.add_image(emissive)
            emissive_tex = gltf.Texture(source=emissive, sampler=self.document.samplers[0])
            self.document.add_texture(emissive_tex)
            diffuse_tex_info = gltf.TextureInfo(index=emissive_tex)

            mesh_material.emissiveTexture = diffuse_tex_info
        if len(textures) > 3:
            height = gltf.Image(uri=textures[3])

        self.document.add_material(mesh_material)

        self.buffers.append(vertex_data)
        self.buffers.append(index_data)

        self.buffer = gltf.Buffer(self.byteLength(self.buffers), uri=self.bin_path, name="Default Buffer")

        vertex_buffer_views = self.generate_structured_array_buffer_views(vertex_data, self.buffer, gltf.BufferTarget.ARRAY_BUFFER,
                                                                     offset=self.offset, name=mesh_name + "{key} Buffer View")

        self.offset += vertex_data.nbytes
        print(self.offset)
        index_buffer_view = self.generate_array_buffer_view(index_data, self.buffer, gltf.BufferTarget.ELEMENT_ARRAY_BUFFER,
                                                       offset=self.offset, name=mesh_name + "Index Buffer View")

        self.offset += index_data.nbytes
        print(self.offset)

        vertex_accessors = self.generate_structured_array_accessors(vertex_data, vertex_buffer_views, name=mesh_name + "{key} Accessor")
        index_accessor = self.generate_array_accessor(index_data, index_buffer_view, name=mesh_name + "Index Accessor")

        primitive = gltf.Primitive(vertex_accessors, index_accessor, mesh_material, gltf.PrimitiveMode.TRIANGLES)

        self.document.add_buffer_views(vertex_buffer_views.values())
        self.document.add_buffer_view(index_buffer_view)

        self.document.add_accessors(vertex_accessors.values())
        self.document.add_accessor(index_accessor)

        mesh.primitives.append(primitive)
        self.document.add_mesh(mesh)
        loc, rot, sca = transform_matrix.decompose()
        loc = [loc.x, loc.y, loc.z]
        rot = [rot.x, rot.y, rot.z, rot.w]
        sca = [sca.x, sca.y, sca.z]

        self.document.add_node(gltf.Node(name=mesh_name, mesh=mesh, translation=loc, rotation=rot, scale=sca))


    def save(self):
        self.document.add_buffer(self.buffer)
        self.document.add_scene(gltf.Scene(name=self.filename, nodes=self.document.nodes))
        data = self.document.togltf()
        with open(self.gltf_path, 'w') as f:
            json.dump(data, f, indent=2)

        with open(self.bin_path, 'wb') as f:
            for buffer in self.buffers:
                f.write(buffer.tobytes())

    def __init__(self, name, gltf_path, bin_path):
        self.document = gltf.Document()
        self.offset = 0
        self.document.add_sampler(gltf.Sampler())
        self.filename = name
        self.gltf_path = gltf_path
        self.bin_path = bin_path
