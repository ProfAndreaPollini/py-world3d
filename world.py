from pathlib import Path
from typing import Optional
from pyrr import Matrix44
import sys

import glm
import moderngl as mgl

import moderngl as mlg

import moderngl_window as mglw
from moderngl_window import geometry
from moderngl_window.scene.camera import KeyboardCamera

from PIL import Image, ImageOps
from window import CameraWindow


import math

import numpy
import moviepy.editor as mp

from moderngl_window.opengl.vao import VAO
from moderngl_window.geometry import AttributeNames


Image.MAX_IMAGE_PIXELS = None

frames = []


def sphere(
    radius=1.0,
    sectors=32,
    rings=16,
    normals=True,
    uvs=True,
    name: str = None,
    attr_names=AttributeNames,
    heightmap: Optional[Image.Image] = None,
    bath: Optional[Image.Image] = None
) -> VAO:
    """Creates a sphere.
    Keyword Args:
        radius (float): Radius or the sphere
        rings (int): number or horizontal rings
        sectors (int): number of vertical segments
        normals (bool): Include normals in the VAO
        uvs (bool): Include texture coordinates in the VAO
        name (str): An optional name for the VAO
        attr_names (AttributeNames): Attribute names
    Returns:
        A :py:class:`VAO` instance
    """
    R = 1.0 / (rings - 1)
    S = 1.0 / (sectors - 1)

    vertices = [0] * (rings * sectors * 3)
    normals = [0] * (rings * sectors * 3)
    uvs = [0] * (rings * sectors * 2)

    v, n, t = 0, 0, 0
    for r in range(rings):
        for s in range(sectors):
            y = math.sin(-math.pi / 2 + math.pi * r * R)
            x = math.cos(2 * math.pi * s * S) * math.sin(math.pi * r * R)
            z = math.sin(2 * math.pi * s * S) * math.sin(math.pi * r * R)

            uvs[t] = s * S
            uvs[t + 1] = r * R
            vertex = glm.vec3(x, y, z)
            vertex_dir = glm.normalize(vertex)
            real_radius = radius
            if heightmap:
                w, h = heightmap.size
                px, py = glm.floor((w-1)*uvs[t]), glm.floor((h-1)*uvs[t + 1])
                c = heightmap.getpixel((px, py))[0]
                if c != 0:

                    # vertex_dir = glm.normalize(vertex)
                    real_radius += c
                    vertex += 0.05*vertex_dir * (c/255.0)
                    # print(x, y, z, end=" <-> ")
                    x, y, z = vertex.to_tuple()
                    # print(x, y, z)
            if bath:
                w, h = bath.size
                px, py = glm.floor((w-1)*uvs[t]), glm.floor((h-1)*uvs[t + 1])
                c = 255 - bath.getpixel((px, py))[0]
                if c != 0:
                    # vertex = glm.vec3(x, y, z)

                    real_radius += c
                    vertex -= 0.1*vertex_dir * (c/255.0)
                    # print(x, y, z, end=" <-> ")
                    x, y, z = vertex.to_tuple()
                # print(x, y, z)
            vertices[v] = x * radius
            vertices[v + 1] = y * radius
            vertices[v + 2] = z * radius

            normals[n] = x
            normals[n + 1] = y
            normals[n + 2] = z

            t += 2
            v += 3
            n += 3

    indices = [0] * rings * sectors * 6
    i = 0
    for r in range(rings - 1):
        for s in range(sectors - 1):
            indices[i] = r * sectors + s
            indices[i + 1] = (r + 1) * sectors + (s + 1)
            indices[i + 2] = r * sectors + (s + 1)

            indices[i + 3] = r * sectors + s
            indices[i + 4] = (r + 1) * sectors + s
            indices[i + 5] = (r + 1) * sectors + (s + 1)
            i += 6

    vao = VAO(name or "sphere", mode=mlg.TRIANGLES)

    vbo_vertices = numpy.array(vertices, dtype=numpy.float32)
    vao.buffer(vbo_vertices, "3f", [attr_names.POSITION])

    if normals:
        vbo_normals = numpy.array(normals, dtype=numpy.float32)
        vao.buffer(vbo_normals, "3f", [attr_names.NORMAL])

    if uvs:
        vbo_uvs = numpy.array(uvs, dtype=numpy.float32)
        vao.buffer(vbo_uvs, "2f", [attr_names.TEXCOORD_0])

    vbo_elements = numpy.array(indices, dtype=numpy.uint32)
    vao.index_buffer(vbo_elements, index_element_size=4)

    return vao


class WorldModel(CameraWindow):
    title = 'GL Transmission Format (glTF) 2.0 Scene'
    window_size = 900, 1600
    aspect_ratio = None

    resource_dir = (Path(__file__).parent).resolve()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.wnd.mouse_exclusivity = True
        self.heightmap = Image.open("./elevation.png").convert('RGB')
        self.heightmap = ImageOps.mirror(ImageOps.flip(self.heightmap))
        self.bath = Image.open("./bath.png").convert('RGB')
        self.bath = ImageOps.mirror(ImageOps.flip(self.bath))
        self.cube = sphere(rings=400, sectors=400,
                           heightmap=self.heightmap, bath=self.bath)
        self.sea = sphere(rings=400, sectors=400)
        self.texture = self.load_texture_2d(
            "./world.jpg", mipmap=True, flip_x=True)

        self.prog = self.load_program('shaders/simple.glsl')
        self.prog_water = self.load_program('shaders/simple_water.glsl')
        # self.prog['color'].value = 1.0, 1.0, 1.0, 1.0  # type: ignore

    def render(self, time: float, frametime: float):
        self.ctx.enable_only(mgl.CULL_FACE | mgl.DEPTH_TEST)  # type: ignore

        rotation = Matrix44.from_eulers((0, 0, time/5.0), dtype='f4')
        translation = Matrix44.from_translation((0.0, 0.0, -3.5), dtype='f4')
        modelview = translation * rotation

        self.prog['m_proj'].write(
            self.camera.projection.matrix)  # type: ignore
        self.prog['m_model'].write(modelview)  # type: ignore
        self.prog['m_camera'].write(self.camera.matrix)  # type: ignore
        self.prog_water['m_proj'].write(
            self.camera.projection.matrix)  # type: ignore
        self.prog_water['m_model'].write(modelview)  # type: ignore
        self.prog_water['m_camera'].write(self.camera.matrix)  # type: ignore
        # fbo = self.ctx.simple_framebuffer(self.window_size)
        # fbo.use()
        # self.sea.render(self.prog_water)
        self.texture.use(location=0)

        self.cube.render(self.prog)

        self.ctx.finish()

        frames.append(numpy.flipud(numpy.frombuffer(
            self.wnd.fbo.read(components=4, dtype='f1'), dtype='uint8').reshape(
                (*self.wnd.fbo.size[1::-1], 4))))
        if time > 20.0:
            clip = mp.ImageSequenceClip(frames, fps=60)

            # Salva il video
            clip.write_videofile("output.mp4")
            self.close()
            sys.exit()


if __name__ == '__main__':
    mglw.run_window_config(WorldModel)
