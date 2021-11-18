/*=========================================================================
 *
 *  Copyright NumFOCUS
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *         http://www.apache.org/licenses/LICENSE-2.0.txt
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 *
 *=========================================================================*/
#ifndef itkDataJSON_h
#define itkDataJSON_h
#include "WebAssemblyInterfaceExport.h"


#include "itkDataObject.h"
#include <string>

namespace itk
{
/** \class DataJSON
 * \brief JSON representation for an itk::DataObject
 *
 * JSON representation for itk::DataObject's for interfacing across programming languages and runtimes.
 * 
 * Binary array buffer's are stored as strings with memory addresses or paths on disks or a virtual filesystem.
 * 
 * \ingroup WebAssemblyInterface
 */
class WebAssemblyInterface_EXPORT DataJSON : public DataObject
{
public:
  ITK_DISALLOW_COPY_AND_MOVE(DataJSON);

  /** Standard smart pointer declarations */
  using Self = DataJSON;
  using Superclass = DataObject;
  using Pointer = SmartPointer<Self>;
  using ConstPointer = SmartPointer<const Self>;
  itkNewMacro(Self);
  itkTypeMacro(DataJSON, DataObject);

  /** Get/Set the DataObject JSON representation. */
  itkSetStringMacro(JSON);
  itkGetStringMacro(JSON);

  /** Get/Set the DataObject used to generate the JSON representation.
   * 
   * We hold a reference to this object. */
  itkGetConstObjectMacro(DataObject, DataObject);
  itkSetObjectMacro(DataObject, DataObject);

protected:
  DataJSON() = default;
  ~DataJSON() override = default;
  void
  PrintSelf(std::ostream & os, Indent indent) const override;

  std::string m_JSON;
  DataObject::ConstPointer m_DataObject;
};
} // end namespace itk

#endif
