import json
from pathlib import Path
from dataclasses import asdict
from typing import List, Union, Dict, Tuple

import numpy as np

from .interface_types import InterfaceTypes
from .pipeline_input import PipelineInput
from .pipeline_output import PipelineOutput
from .text_stream import TextStream
from .binary_stream import BinaryStream
from .text_file import TextFile
from .binary_file import BinaryFile
from .image import Image
from .mesh import Mesh
from .polydata import PolyData
from .int_types import IntTypes
from .float_types import FloatTypes

from wasmer import engine, wasi, Store, Module, ImportObject, Instance
from wasmer_compiler_cranelift import Compiler

def _memoryview_to_numpy_array(component_type, buf):
    if component_type == IntTypes.UInt8:
        return np.frombuffer(buf, dtype=np.uint8).copy()
    elif component_type == IntTypes.Int8:
        return np.frombuffer(buf, dtype=np.int8).copy()
    elif component_type == IntTypes.UInt16:
        return np.frombuffer(buf, dtype=np.uint16).copy()
    elif component_type == IntTypes.Int16:
        return np.frombuffer(buf, dtype=np.int16).copy()
    elif component_type == IntTypes.UInt32:
        return np.frombuffer(buf, dtype=np.uint32).copy()
    elif component_type == IntTypes.Int32:
        return np.frombuffer(buf, dtype=np.int32).copy()
    elif component_type == IntTypes.UInt64:
        return np.frombuffer(buf, dtype=np.uint64).copy()
    elif component_type == IntTypes.Int64:
        return np.frombuffer(buf, dtype=np.int64).copy()
    elif component_type == FloatTypes.Float32:
        return np.frombuffer(buf, dtype=np.float32).copy()
    elif component_type == FloatTypes.Float64:
        return np.frombuffer(buf, dtype=np.float64).copy()
    else:
        raise ValueError('Unsupported component type')


class Pipeline:
    """Run an itk-wasm WASI pipeline."""

    def __init__(self, pipeline: Union[str, Path, bytes]):
        """Compile the pipeline."""
        self.engine = engine.Universal(Compiler)
        if isinstance(pipeline, bytes):
            wasm_bytes = pipeline
        else:
            with open(pipeline, 'rb') as fp:
                wasm_bytes = fp.read()
        self.store = Store(self.engine)
        self.module = Module(self.store, wasm_bytes)
        self.wasi_version = wasi.get_version(self.module, strict=True)

    def run(self, args: List[str], outputs: List[PipelineOutput]=[], inputs: List[PipelineInput]=[]) -> Tuple[PipelineOutput]:
        """Run the itk-wasm pipeline."""

        preopen_directories=set()
        map_directories={}
        # Todo: expose?
        environments={}
        for index, input_ in enumerate(inputs):
            if input_.type == InterfaceTypes.TextFile or input_.type == InterfaceTypes.BinaryFile:
                preopen_directories.add(str(input_.data.path.parent))
        for index, output in enumerate(outputs):
            if output.type == InterfaceTypes.TextFile or output.type == InterfaceTypes.BinaryFile:
                preopen_directories.add(str(output.data.path.parent))
        preopen_directories = list(preopen_directories)

        wasi_state = wasi.StateBuilder('itk-wasm-pipeline')
        wasi_state.arguments(args)
        wasi_state.environments(environments)
        wasi_state.map_directories(map_directories)
        wasi_state.preopen_directories(preopen_directories)
        wasi_env = wasi_state.finalize()
        import_object = wasi_env.generate_import_object(self.store, self.wasi_version)

        instance = Instance(self.module, import_object)
        self.memory = instance.exports.memory
        self.input_array_alloc = instance.exports.itk_wasm_input_array_alloc
        self.input_json_alloc = instance.exports.itk_wasm_input_json_alloc
        self.output_array_address = instance.exports.itk_wasm_output_array_address
        self.output_array_size = instance.exports.itk_wasm_output_array_size
        self.output_json_address = instance.exports.itk_wasm_output_json_address
        self.output_json_size = instance.exports.itk_wasm_output_json_size

        _initialize = instance.exports._initialize
        _initialize()

        for index, input_ in enumerate(inputs):
            if input_.type == InterfaceTypes.TextStream:
                data_array = input_.data.data.encode()
                array_ptr = self._set_input_array(data_array, index, 0)
                data_json = { "size": len(data_array), "data": f"data:application/vnd.itk.address,0:{array_ptr}" }
                self._set_input_json(data_json, index)
            elif input_.type == InterfaceTypes.BinaryStream:
                data_array = input_.data.data
                array_ptr = self._set_input_array(data_array, index, 0)
                data_json = { "size": len(data_array), "data": f"data:application/vnd.itk.address,0:{array_ptr}" }
                self._set_input_json(data_json, index)
            elif input_.type == InterfaceTypes.TextFile:
                pass
            elif input_.type == InterfaceTypes.BinaryFile:
                pass
            elif input_.type == InterfaceTypes.Image:
                image = input_.data
                mv = bytes(image.data.data)
                data_ptr = self._set_input_array(mv, index, 0)
                dv = bytes(image.direction.data)
                direction_ptr = self._set_input_array(dv, index, 1)
                image_json = {
                    "imageType": asdict(image.imageType),
                    "name": image.name,
                    "origin": image.origin,
                    "spacing": image.spacing,
                    "direction": f"data:application/vnd.itk.address,0:{direction_ptr}",
                    "size": image.size,
                    "data": f"data:application/vnd.itk.address,0:{data_ptr}"
                }
                self._set_input_json(image_json, index)
            elif input_.type == InterfaceTypes.Mesh:
                mesh = input_.data
                if mesh.numberOfPoints:
                    pv = bytes(mesh.points)
                else:
                    pv = bytes([])
                points_ptr = self._set_input_array(pv, index, 0)
                if mesh.numberOfCells:
                    cv = bytes(mesh.cells)
                else:
                    cv = bytes([])
                cells_ptr = self._set_input_array(cv, index, 1)
                if mesh.numberOfPointPixels:
                    pdv = bytes(mesh.pointData)
                else:
                    pdv = bytes([])
                point_data_ptr = self._set_input_array(pdv, index, 2)
                if mesh.numberOfCellPixels:
                    cdv = bytes(mesh.cellData)
                else:
                    cdv = bytes([])
                cell_data_ptr = self._set_input_array(cdv, index, 3)
                mesh_json = {
                    "meshType": asdict(mesh.meshType),
                    "name": mesh.name,

                    "numberOfPoints": mesh.numberOfPoints,
                    "points": f"data:application/vnd.itk.address,0:{points_ptr}",

                    "numberOfCells": mesh.numberOfCells,
                    "cells": f"data:application/vnd.itk.address,0:{cells_ptr}",
                    "cellBufferSize": mesh.cellBufferSize,

                    "numberOfPointPixels": mesh.numberOfPointPixels,
                    "pointData": f"data:application/vnd.itk.address,0:{point_data_ptr}",

                    "numberOfCellPixels": mesh.numberOfCellPixels,
                    "cellData": f"data:application/vnd.itk.address,0:{cell_data_ptr}",
                }
                self._set_input_json(mesh_json, index)
            elif input_.type == InterfaceTypes.PolyData:
                polydata = input_.data
                if polydata.numberOfPoints:
                    pv = bytes(polydata.points)
                else:
                    pv = bytes([])
                points_ptr = self._set_input_array(pv, index, 0)

                if polydata.verticesBufferSize:
                    pv = bytes(polydata.vertices)
                else:
                    pv = bytes([])
                vertices_ptr = self._set_input_array(pv, index, 1)

                if polydata.linesBufferSize:
                    pv = bytes(polydata.lines)
                else:
                    pv = bytes([])
                lines_ptr = self._set_input_array(pv, index, 2)

                if polydata.polygonsBufferSize:
                    pv = bytes(polydata.polygons)
                else:
                    pv = bytes([])
                polygons_ptr = self._set_input_array(pv, index, 3)

                if polydata.triangleStripsBufferSize:
                    pv = bytes(polydata.triangleStrips)
                else:
                    pv = bytes([])
                triangleStrips_ptr = self._set_input_array(pv, index, 4)

                if polydata.numberOfPointPixels:
                    pv = bytes(polydata.pointData)
                else:
                    pv = bytes([])
                pointData_ptr = self._set_input_array(pv, index, 5)

                if polydata.numberOfCellPixels:
                    pv = bytes(polydata.cellData)
                else:
                    pv = bytes([])
                cellData_ptr = self._set_input_array(pv, index, 6)

                polydata_json = {
                    "polyDataType": asdict(polydata.polyDataType),
                    "name": polydata.name,

                    "numberOfPoints": polydata.numberOfPoints,
                    "points": f"data:application/vnd.itk.address,0:{points_ptr}",

                    "verticesBufferSize": polydata.verticesBufferSize,
                    "vertices": f"data:application/vnd.itk.address,0:{vertices_ptr}",

                    "linesBufferSize": polydata.linesBufferSize,
                    "lines": f"data:application/vnd.itk.address,0:{lines_ptr}",

                    "polygonsBufferSize": polydata.polygonsBufferSize,
                    "polygons": f"data:application/vnd.itk.address,0:{polygons_ptr}",

                    "triangleStripsBufferSize": polydata.triangleStripsBufferSize,
                    "triangleStrips": f"data:application/vnd.itk.address,0:{triangleStrips_ptr}",

                    "numberOfPointPixels": polydata.numberOfPointPixels,
                    "pointData": f"data:application/vnd.itk.address,0:{pointData_ptr}",

                    "numberOfCellPixels": polydata.numberOfCellPixels,
                    "cellData": f"data:application/vnd.itk.address,0:{cellData_ptr}"
                }
                self._set_input_json(polydata_json, index)
            else:
                raise ValueError(f'Unexpected/not yet supported input.type {input_.type}')

        delayed_start = instance.exports.itk_wasm_delayed_start
        return_code = delayed_start()

        populated_outputs: List[PipelineOutput] = []
        if len(outputs) and return_code == 0:
            for index, output in enumerate(outputs):
                output_data = None
                if output.type == InterfaceTypes.TextStream:
                    data_ptr = self.output_array_address(0, index, 0)
                    data_size = self.output_array_size(0, index, 0)
                    data_array_view = bytearray(memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    output_data = PipelineOutput(InterfaceTypes.TextStream, TextStream(data_array_view.decode()))
                elif output.type == InterfaceTypes.BinaryStream:
                    data_ptr = self.output_array_address(0, index, 0)
                    data_size = self.output_array_size(0, index, 0)
                    data_array = bytes(memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    output_data = PipelineOutput(InterfaceTypes.BinaryStream, BinaryStream(data_array))
                elif output.type == InterfaceTypes.TextFile:
                    output_data = PipelineOutput(InterfaceTypes.TextFile, TextFile(output.data.path))
                elif output.type == InterfaceTypes.BinaryFile:
                    output_data = PipelineOutput(InterfaceTypes.BinaryFile, BinaryFile(output.data.path))
                elif output.type == InterfaceTypes.Image:
                    image_json = self._get_output_json(index)

                    image = Image(**image_json)

                    data_ptr = self.output_array_address(0, index, 0)
                    data_size = self.output_array_size(0, index, 0)
                    data_array = _memoryview_to_numpy_array(image.imageType.componentType, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    image.data = data_array

                    direction_ptr = self.output_array_address(0, index, 1)
                    direction_size = self.output_array_size(0, index, 1)
                    direction_array = _memoryview_to_numpy_array(FloatTypes.Float64, memoryview(self.memory.buffer)[direction_ptr:direction_ptr+direction_size])
                    dimension = image.imageType.dimension
                    direction_array.shape = (dimension, dimension)
                    image.direction = direction_array

                    output_data = PipelineOutput(InterfaceTypes.Image, image)
                elif output.type == InterfaceTypes.Mesh:
                    mesh_json = self._get_output_json(index)
                    mesh = Mesh(**mesh_json)

                    if mesh.numberOfPoints > 0:
                        data_ptr = self.output_array_address(0, index, 0)
                        data_size = self.output_array_size(0, index, 0)
                        mesh.points = _memoryview_to_numpy_array(mesh.meshType.pointComponentType, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        mesh.points =  _memoryview_to_numpy_array(mesh.meshType.pointComponentType, bytes([]))

                    if mesh.numberOfCells > 0:
                        data_ptr = self.output_array_address(0, index, 1)
                        data_size = self.output_array_size(0, index, 1)
                        mesh.cells = _memoryview_to_numpy_array(mesh.meshType.cellComponentType, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        mesh.cells =  _memoryview_to_numpy_array(mesh.meshType.cellComponentType, bytes([]))
                    if mesh.numberOfPointPixels > 0:
                        data_ptr = self.output_array_address(0, index, 2)
                        data_size = self.output_array_size(0, index, 2)
                        mesh.pointData = _memoryview_to_numpy_array(mesh.meshType.pointPixelComponentType, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        mesh.pointData =  _memoryview_to_numpy_array(mesh.meshType.pointPixelComponentType, bytes([]))

                    if mesh.numberOfCellPixels > 0:
                        data_ptr = self.output_array_address(0, index, 3)
                        data_size = self.output_array_size(0, index, 3)
                        mesh.cellData = _memoryview_to_numpy_array(mesh.meshType.cellPixelComponentType, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        mesh.cellData =  _memoryview_to_numpy_array(mesh.meshType.cellPixelComponentType, bytes([]))

                    output_data = PipelineOutput(InterfaceTypes.Mesh, mesh)
                elif output.type == InterfaceTypes.PolyData:
                    polydata_json = self._get_output_json(index)
                    polydata = PolyData(**polydata_json)

                    if polydata.numberOfPoints > 0:
                        data_ptr = self.output_array_address(0, index, 0)
                        data_size = self.output_array_size(0, index, 0)
                        polydata.points = _memoryview_to_numpy_array(FloatTypes.Float32, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        polydata.points =  _memoryview_to_numpy_array(FloatTypes.Float32, bytes([]))

                    if polydata.verticesBufferSize > 0:
                        data_ptr = self.output_array_address(0, index, 1)
                        data_size = self.output_array_size(0, index, 1)
                        polydata.vertices = _memoryview_to_numpy_array(IntTypes.UInt32, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        polydata.vertices =  _memoryview_to_numpy_array(IntTypes.UInt32, bytes([]))

                    if polydata.linesBufferSize > 0:
                        data_ptr = self.output_array_address(0, index, 2)
                        data_size = self.output_array_size(0, index, 2)
                        polydata.lines = _memoryview_to_numpy_array(IntTypes.UInt32, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        polydata.lines =  _memoryview_to_numpy_array(IntTypes.UInt32, bytes([]))

                    if polydata.polygonsBufferSize > 0:
                        data_ptr = self.output_array_address(0, index, 3)
                        data_size = self.output_array_size(0, index, 3)
                        polydata.polygons = _memoryview_to_numpy_array(IntTypes.UInt32, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        polydata.polygons =  _memoryview_to_numpy_array(IntTypes.UInt32, bytes([]))

                    if polydata.triangleStripsBufferSize > 0:
                        data_ptr = self.output_array_address(0, index, 4)
                        data_size = self.output_array_size(0, index, 4)
                        polydata.triangleStrips = _memoryview_to_numpy_array(IntTypes.UInt32, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        polydata.triangleStrips =  _memoryview_to_numpy_array(IntTypes.UInt32, bytes([]))

                    if polydata.numberOfPointPixels > 0:
                        data_ptr = self.output_array_address(0, index, 5)
                        data_size = self.output_array_size(0, index, 5)
                        polydata.pointData = _memoryview_to_numpy_array(polydata.polyDataType.pointPixelComponentType, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        polydata.triangleStrips =  _memoryview_to_numpy_array(polydata.polyDataType.pointPixelComponentType, bytes([]))

                    if polydata.numberOfCellPixels > 0:
                        data_ptr = self.output_array_address(0, index, 6)
                        data_size = self.output_array_size(0, index, 6)
                        polydata.cellData = _memoryview_to_numpy_array(polydata.polyDataType.cellPixelComponentType, memoryview(self.memory.buffer)[data_ptr:data_ptr+data_size])
                    else:
                        polydata.triangleStrips =  _memoryview_to_numpy_array(polydata.polyDataType.cellPixelComponentType, bytes([]))

                    output_data = PipelineOutput(InterfaceTypes.PolyData, polydata)

                populated_outputs.append(output_data)

        delayed_exit = instance.exports.itk_wasm_delayed_exit
        delayed_exit(return_code)

        # Should we be returning the return_code?
        return tuple(populated_outputs)

    def _set_input_array(self, data_array: Union[bytes, bytearray], input_index: int, sub_index: int) -> int:
        data_ptr = 0
        if data_array != None:
            data_ptr = self.input_array_alloc(0, input_index, sub_index, len(data_array))
            buf = memoryview(self.memory.buffer)
            buf[data_ptr:data_ptr+len(data_array)] = data_array
        return data_ptr

    def _set_input_json(self, data_object: Dict, input_index: int) -> None:
        data_json = json.dumps(data_object).encode()
        json_ptr = self.input_json_alloc(0, input_index, len(data_json))
        buf = memoryview(self.memory.buffer)
        buf[json_ptr:json_ptr+len(data_json)] = data_json

    def _get_output_json(self, output_index: int) -> Dict:
        json_ptr = self.output_json_address(0, output_index)
        json_len = self.output_json_size(0, output_index)
        json_str = bytes(memoryview(self.memory.buffer)[json_ptr:json_ptr+json_len]).decode()
        json_result = json.loads(json_str)
        return json_result
