/*=========================================================================
 *
 *  Copyright NumFOCUS
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *         https://www.apache.org/licenses/LICENSE-2.0.txt
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 *
 *=========================================================================*/
#ifndef itkWasmImageToImageFilter_hxx
#define itkWasmImageToImageFilter_hxx

#include "itkWasmImageToImageFilter.h"

#include "itkMetaDataDictionaryJSON.h"
#include "itkImportVectorImageFilter.h"
#include <exception>
#include "itkWasmMapComponentType.h"
#include "itkWasmMapPixelType.h"
#include "itkDefaultConvertPixelTraits.h"
#include "itkMetaDataObject.h"

#include "rapidjson/document.h"

namespace itk
{

template <typename TImage>
WasmImageToImageFilter<TImage>
::WasmImageToImageFilter()
{
  this->SetNumberOfRequiredInputs(1);

  typename ImageType::Pointer output = static_cast<ImageType *>(this->MakeOutput(0).GetPointer());
  this->ProcessObject::SetNumberOfRequiredOutputs(1);
  this->ProcessObject::SetNthOutput(0, output.GetPointer());
}

template <typename TImage>
ProcessObject::DataObjectPointer
WasmImageToImageFilter<TImage>
::MakeOutput(ProcessObject::DataObjectPointerArraySizeType)
{
  return ImageType::New().GetPointer();
}

template <typename TImage>
ProcessObject::DataObjectPointer
WasmImageToImageFilter<TImage>
::MakeOutput(const ProcessObject::DataObjectIdentifierType &)
{
  return ImageType::New().GetPointer();
}

template <typename TImage>
auto
WasmImageToImageFilter<TImage>
::GetOutput() -> ImageType *
{
  // we assume that the first output is of the templated type
  return itkDynamicCastInDebugMode<ImageType *>(this->GetPrimaryOutput());
}

template <typename TImage>
auto
WasmImageToImageFilter<TImage>
::GetOutput() const -> const ImageType *
{
  // we assume that the first output is of the templated type
  return itkDynamicCastInDebugMode<const ImageType *>(this->GetPrimaryOutput());
}

template <typename TImage>
auto
WasmImageToImageFilter<TImage>
::GetOutput(unsigned int idx) -> ImageType *
{
  auto * out = dynamic_cast<ImageType *>(this->ProcessObject::GetOutput(idx));

  if (out == nullptr && this->ProcessObject::GetOutput(idx) != nullptr)
  {
    itkWarningMacro(<< "Unable to convert output number " << idx << " to type " << typeid(ImageType).name());
  }
  return out;
}

template <typename TImage>
void
WasmImageToImageFilter<TImage>
::SetInput(const WasmImageType * input)
{
  // Process object is not const-correct so the const_cast is required here
  this->ProcessObject::SetNthInput(0, const_cast<WasmImageType *>(input));
}

template <typename TImage>
void
WasmImageToImageFilter<TImage>
::SetInput(unsigned int index, const WasmImageType * image)
{
  // Process object is not const-correct so the const_cast is required here
  this->ProcessObject::SetNthInput(index, const_cast<WasmImageType *>(image));
}

template <typename TImage>
const typename WasmImageToImageFilter<TImage>::WasmImageType *
WasmImageToImageFilter<TImage>
::GetInput()
{
  return itkDynamicCastInDebugMode<const WasmImageType *>(this->GetPrimaryInput());
}

template <typename TImage>
const typename WasmImageToImageFilter<TImage>::WasmImageType *
WasmImageToImageFilter<TImage>
::GetInput(unsigned int idx)
{
  return itkDynamicCastInDebugMode<const TImage *>(this->ProcessObject::GetInput(idx));
}

template <typename TImage>
void
WasmImageToImageFilter<TImage>
::GenerateData()
{
  // Get the input and output pointers
  const WasmImageType * imageJSON = this->GetInput();
  const std::string json(imageJSON->GetJSON());
  ImageType * image = this->GetOutput();

  using IOPixelType = typename TImage::IOPixelType;
  using PixelType = typename TImage::PixelType;
  using ConvertPixelTraits = DefaultConvertPixelTraits<PixelType>;
  constexpr unsigned int Dimension = TImage::ImageDimension;

  rapidjson::Document document;
  if (document.Parse(json.c_str()).HasParseError())
    {
    throw std::runtime_error("Could not parse JSON");
    }

  const rapidjson::Value & imageType = document["imageType"];
  const int dimension = imageType["dimension"].GetInt();
  if (dimension != Dimension)
  {
    throw std::runtime_error("Unexpected dimension");
  }
  const std::string componentType( imageType["componentType"].GetString() );
  if ( componentType != itk::wasm::MapComponentType<typename ConvertPixelTraits::ComponentType>::ComponentString )
  {
    throw std::runtime_error("Unexpected component type");
  }

  const std::string pixelType( imageType["pixelType"].GetString() );
  if ( pixelType != itk::wasm::MapPixelType<PixelType>::PixelString )
  {
    throw std::runtime_error("Unexpected pixel type");
  }

  using FilterType = ImportVectorImageFilter< TImage >;
  auto filter = FilterType::New();

  // Don't throw when PixelType is VariableLengthPixel where number of components is 0
  if (ConvertPixelTraits::GetNumberOfComponents() != 0 && imageType["components"].GetInt() != ConvertPixelTraits::GetNumberOfComponents() )
  {
    throw std::runtime_error("Unexpected number of components");
  }

  using OriginType = typename ImageType::PointType;
  OriginType origin;
  const rapidjson::Value & originJson = document["origin"];
  int count = 0;
  for( rapidjson::Value::ConstValueIterator itr = originJson.Begin(); itr != originJson.End(); ++itr )
    {
    origin[count] = itr->GetDouble();
    ++count;
    }
  filter->SetOrigin( origin );

  using SpacingType = typename ImageType::SpacingType;
  SpacingType spacing;
  const rapidjson::Value & spacingJson = document["spacing"];
  count = 0;
  for( rapidjson::Value::ConstValueIterator itr = spacingJson.Begin(); itr != spacingJson.End(); ++itr )
    {
    spacing[count] = itr->GetDouble();
    ++count;
    }
  filter->SetSpacing( spacing );

  using DirectionType = typename ImageType::DirectionType;
  const rapidjson::Value & directionJson = document["direction"];
  const std::string directionString( directionJson.GetString() );
  const double * directionPtr = reinterpret_cast< double * >( std::strtoull(directionString.substr(35).c_str(), nullptr, 10) );
  using VnlMatrixType = typename DirectionType::InternalMatrixType;
  const VnlMatrixType vnlMatrix(directionPtr);
  const DirectionType direction(vnlMatrix);
  filter->SetDirection(direction);

  using SizeType = typename ImageType::SizeType;
  SizeType size;
  const rapidjson::Value & sizeJson = document["size"];
  count = 0;
  SizeValueType totalSize = 1;
  for( rapidjson::Value::ConstValueIterator itr = sizeJson.Begin(); itr != sizeJson.End(); ++itr )
    {
    size[count] = itr->GetInt();
    totalSize *= size[count];
    ++count;
    }
  using RegionType = typename ImageType::RegionType;
  RegionType region;
  region.SetSize( size );
  filter->SetRegion( region );

  const rapidjson::Value & dataJson = document["data"];
  const std::string dataString( dataJson.GetString() );
  IOPixelType * dataPtr = reinterpret_cast< IOPixelType * >( std::strtoull(dataString.substr(35).c_str(), nullptr, 10) );
  const bool letImageContainerManageMemory = false;
  if (pixelType == "VariableLengthVector" || pixelType == "VariableSizeMatrix")
    {
    filter->SetImportPointer( dataPtr, totalSize, letImageContainerManageMemory, imageType["components"].GetInt());
    }
  else
    {
    filter->SetImportPointer( dataPtr, totalSize, letImageContainerManageMemory);
    }
  filter->Update();
  image->Graft(filter->GetOutput());

  if (document.HasMember("metadata"))
  {
    auto dictionary = image->GetMetaDataDictionary();
    const rapidjson::Value & metadataJson = document["metadata"];
    wasm::ConvertJSONToMetaDataDictionary(metadataJson, dictionary);
  }

}

template <typename TImage>
void
WasmImageToImageFilter<TImage>
::PrintSelf(std::ostream & os, Indent indent) const
{
  Superclass::PrintSelf(os, indent);
}
} // end namespace itk

#endif
