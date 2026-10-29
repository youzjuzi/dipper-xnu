/** @file
  XnuLoaderDxe: registers the XNU loader application of this firmware volume as a boot option.

  Adapted from UniXNU's UniXNUDxe (BSD-2-Clause-Patent). Differences: the file GUID is fixed here, the
  option is appended to BootOrder instead of put first, and it has no optional data.
**/

#include <PiDxe.h>

#include <Guid/GlobalVariable.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DebugLib.h>
#include <Library/DevicePathLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/PrintLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>
#include <Protocol/FirmwareVolume2.h>
#include <Protocol/LoadedImage.h>

#define OPTION_ATTRIBUTES  (EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS | EFI_VARIABLE_RUNTIME_ACCESS)

// Must match FILE APPLICATION in dipper.fdf.inc
STATIC CONST EFI_GUID  mLoaderFile   = { 0xd82f808b, 0xecca, 0x4bb8, { 0x8e, 0x9f, 0x9b, 0x9b, 0xaf, 0xc4, 0x90, 0xf5 } };
STATIC CONST CHAR16    mDescription[] = L"XNU Loader (HackiOS)";

EFI_STATUS
EFIAPI
XnuLoaderDxeEntry (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS                         Status;
  EFI_LOADED_IMAGE_PROTOCOL          *Loaded;
  MEDIA_FW_VOL_FILEPATH_DEVICE_PATH  Node;
  EFI_DEVICE_PATH_PROTOCOL           *Path;
  UINTN                              PathSize;
  UINTN                              OptionSize;
  UINT8                              *Option;
  UINT8                              *P;
  UINT16                             *Order;
  UINTN                              OrderSize;
  UINT16                             *NewOrder;
  UINT16                             Number;
  UINTN                              Index;
  UINTN                              Out;
  CHAR16                             Name[sizeof ("Boot####")];
  VOID                               *Existing;
  UINTN                              ExistingSize;
  BOOLEAN                            Found;

  Status = gBS->HandleProtocol (ImageHandle, &gEfiLoadedImageProtocolGuid, (VOID **)&Loaded);
  if (EFI_ERROR (Status) || (DevicePathFromHandle (Loaded->DeviceHandle) == NULL)) {
    return EFI_NOT_FOUND;
  }

  EfiInitializeFwVolDevicepathNode (&Node, &mLoaderFile);
  Path = AppendDevicePathNode (DevicePathFromHandle (Loaded->DeviceHandle), (EFI_DEVICE_PATH_PROTOCOL *)&Node);
  if (Path == NULL) {
    return EFI_OUT_OF_RESOURCES;
  }

  // EFI_LOAD_OPTION: Attributes, FilePathListLength, Description, FilePathList
  PathSize   = GetDevicePathSize (Path);
  OptionSize = sizeof (UINT32) + sizeof (UINT16) + sizeof (mDescription) + PathSize;
  Option     = AllocateZeroPool (OptionSize);
  if (Option == NULL) {
    return EFI_OUT_OF_RESOURCES;
  }

  P = Option;
  WriteUnaligned32 ((UINT32 *)P, LOAD_OPTION_ACTIVE);
  P += sizeof (UINT32);
  WriteUnaligned16 ((UINT16 *)P, (UINT16)PathSize);
  P += sizeof (UINT16);
  CopyMem (P, mDescription, sizeof (mDescription));
  P += sizeof (mDescription);
  CopyMem (P, Path, PathSize);
  FreePool (Path);

  Order     = NULL;
  OrderSize = 0;
  GetEfiGlobalVariable2 (EFI_BOOT_ORDER_VARIABLE_NAME, (VOID **)&Order, &OrderSize);

  // Reuse an identical Boot#### if there is one, otherwise take the lowest free number.
  Found  = FALSE;
  Number = 0;
  for (Index = 0; Index < OrderSize / sizeof (UINT16) && !Found; Index++) {
    UnicodeSPrint (Name, sizeof (Name), L"Boot%04x", Order[Index]);
    if (!EFI_ERROR (GetEfiGlobalVariable2 (Name, &Existing, &ExistingSize))) {
      Found = (ExistingSize == OptionSize) && (CompareMem (Existing, Option, OptionSize) == 0);
      if (Found) {
        Number = Order[Index];
      }

      FreePool (Existing);
    }
  }

  if (!Found) {
    for (Number = 0; Number < 0xFFFF; Number++) {
      UnicodeSPrint (Name, sizeof (Name), L"Boot%04x", Number);
      if (EFI_ERROR (GetEfiGlobalVariable2 (Name, &Existing, &ExistingSize))) {
        break;
      }

      FreePool (Existing);
    }

    Status = gRT->SetVariable (Name, &gEfiGlobalVariableGuid, OPTION_ATTRIBUTES, OptionSize, Option);
    if (EFI_ERROR (Status)) {
      DEBUG ((DEBUG_ERROR, "XnuLoaderDxe: cannot write %s: %r\n", Name, Status));
      FreePool (Option);
      return Status;
    }

    Found = TRUE;
  }

  // BootOrder = Number, then everything else in its old order: the loader is the default boot option.
  NewOrder = AllocatePool (OrderSize + sizeof (UINT16));
  if (NewOrder == NULL) {
    FreePool (Option);
    return EFI_OUT_OF_RESOURCES;
  }

  NewOrder[0] = Number;
  for (Index = 0, OrderSize /= sizeof (UINT16), Out = 1; Index < OrderSize; Index++) {
    if (Order[Index] != Number) {
      NewOrder[Out++] = Order[Index];
    }
  }

  {
    Status = gRT->SetVariable (
               EFI_BOOT_ORDER_VARIABLE_NAME, &gEfiGlobalVariableGuid, OPTION_ATTRIBUTES,
               Out * sizeof (UINT16), NewOrder
               );
    DEBUG ((DEBUG_INFO, "XnuLoaderDxe: Boot%04x first in BootOrder: %r\n", Number, Status));
    FreePool (NewOrder);
  }

  FreePool (Option);
  if (Order != NULL) {
    FreePool (Order);
  }

  return EFI_SUCCESS;
}
