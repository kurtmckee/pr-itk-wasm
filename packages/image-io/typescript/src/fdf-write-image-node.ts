// Generated file. To retain edits, remove this comment.

import {
  Image,
  JsonCompatible,
  InterfaceTypes,
  PipelineOutput,
  PipelineInput,
  runPipelineNode
} from 'itk-wasm'

import FdfWriteImageOptions from './fdf-write-image-options.js'
import FdfWriteImageNodeResult from './fdf-write-image-node-result.js'

import path from 'path'

/**
 * Write an itk-wasm file format converted to an image file format
 *
 * @param {Image} image - Input image
 * @param {string} serializedImage - Output image serialized in the file format.
 * @param {FdfWriteImageOptions} options - options object
 *
 * @returns {Promise<FdfWriteImageNodeResult>} - result object
 */
async function fdfWriteImageNode(
  image: Image,
  serializedImage: string,
  options: FdfWriteImageOptions = {}
) : Promise<FdfWriteImageNodeResult> {

  const mountDirs: Set<string> = new Set()

  const desiredOutputs: Array<PipelineOutput> = [
    { type: InterfaceTypes.JsonCompatible },
  ]

  const inputs: Array<PipelineInput> = [
    { type: InterfaceTypes.Image, data: image },
  ]

  const args = []
  // Inputs
  const imageName = '0'
  args.push(imageName)

  // Outputs
  const couldWriteName = '0'
  args.push(couldWriteName)

  const serializedImageName = serializedImage
  args.push(serializedImageName)
  mountDirs.add(path.dirname(serializedImageName))

  // Options
  args.push('--memory-io')
  if (typeof options.informationOnly !== "undefined") {
    options.informationOnly && args.push('--information-only')
  }
  if (typeof options.useCompression !== "undefined") {
    options.useCompression && args.push('--use-compression')
  }

  const pipelinePath = path.join(path.dirname(import.meta.url.substring(7)), 'pipelines', 'fdf-write-image')

  const {
    returnValue,
    stderr,
    outputs
  } = await runPipelineNode(pipelinePath, args, desiredOutputs, inputs, mountDirs)
  if (returnValue !== 0 && stderr !== "") {
    throw new Error(stderr)
  }

  const result = {
    couldWrite: outputs[0]?.data as JsonCompatible,
  }
  return result
}

export default fdfWriteImageNode