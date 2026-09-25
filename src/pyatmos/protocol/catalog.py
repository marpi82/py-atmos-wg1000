"""Register ids copied from the gateway UI bundle ``PRM.js``.

``VERZE_PRM`` in that bundle was 0 when this table was taken.
``Id33`` values are used as raw register ids. Live ACD values use
:func:`hod16_id`, which sets the value-kind bit and the device nibble.
"""

from __future__ import annotations

from enum import IntEnum

from pyatmos.errors import ProtocolError

_LOCAL_ID_MASK = 0xFFFFFF


class Device(IntEnum):
    """High nibble of a packed register id (``PRM_DEV``)."""

    AC33 = 0
    AC16_1 = 1
    AC16_2 = 2
    AC16_3 = 3
    AC16_4 = 4


class ParamKind(IntEnum):
    """Bits 24..27 of a packed register id (``PRM_TYP``)."""

    PARAMETER = 0
    VALUE = 1


class Id33(IntEnum):
    """Gateway configuration slots (``ID33``). Addressed by the raw value."""

    VERZE = 0
    ID_POCET = 1
    LAN_CFG = 2
    LAN_HOSTNAME = 3
    LAN_ETH_DHCP = 4
    LAN_ETH_IP = 5
    LAN_ETH_MASK = 6
    LAN_ETH_GATEWAY = 7
    LAN_AP_DHCP = 8
    LAN_AP_IP = 9
    LAN_AP_MASK = 10
    LAN_AP_GATEWAY = 11
    LAN_AP_CHANNEL = 12
    LAN_AP_WPA = 13
    LAN_AP_SSID1 = 14
    LAN_STA_DHCP = 38
    LAN_STA_IP = 39
    USER1_LANG = 92
    USER1_OKRUH = 93
    USER1_SKIN = 94
    CLOUD_EN = 95
    POCET = 96


class Hod16(IntEnum):
    """Local ids of live ACD registers (``HOD16``)."""

    OBECNE = 0
    AF = 1
    AF_MIN = 2
    AF_MAX = 3
    CAS = 4
    DATUM = 5
    O1_OBECNE = 6
    O2_OBECNE = 7
    O3_OBECNE = 8
    O4_OBECNE = 9
    TUV_OBECNE = 10
    O1_REZIM = 11
    O2_REZIM = 12
    O3_REZIM = 13
    O4_REZIM = 14
    TUV_REZIM = 15
    O1_TRVALY_REZIM = 16
    O2_TRVALY_REZIM = 17
    O3_TRVALY_REZIM = 18
    O4_TRVALY_REZIM = 19
    TUV_TRVALY_REZIM = 20
    O1_TEPLOTA = 21
    O2_TEPLOTA = 22
    O3_TEPLOTA = 23
    O4_TEPLOTA = 24
    TUV_TEPLOTA = 25
    O1_VLHKOST = 26
    O2_VLHKOST = 27
    O3_VLHKOST = 28
    O4_VLHKOST = 29
    TUV_VLHKOST = 30
    O1_TEPLOTY = 31
    O2_TEPLOTY = 32
    O3_TEPLOTY = 33
    O4_TEPLOTY = 34
    TUV_TEPLOTY = 35


def pack_register_id(local_id: int, *, device: Device, kind: ParamKind) -> int:
    """Build a 32-bit register id.

    Args:
        local_id: Id within the device table. Fits in 24 bits.
        device: Device nibble.
        kind: Parameter slot or live value.

    Returns:
        Wire register id.

    Raises:
        ProtocolError: ``local_id`` does not fit in 24 bits.
    """
    if not 0 <= local_id <= _LOCAL_ID_MASK:
        raise ProtocolError(f"local id {local_id} does not fit in 24 bits")
    return local_id | (int(kind) << 24) | (int(device) << 28)


def hod16_id(local_id: Hod16 | int, *, device: Device = Device.AC16_1) -> int:
    """Pack an ACD live-value id.

    Args:
        local_id: ``HOD16`` local id.
        device: Which ACD unit. The UI default is the first unit.

    Returns:
        Wire register id with the value-kind bit set.
    """
    if device is Device.AC33:
        raise ProtocolError("HOD16 registers belong to an ACD unit, not the gateway table")
    return pack_register_id(int(local_id), device=device, kind=ParamKind.VALUE)


def hod33_id(local_id: int) -> int:
    """Pack a gateway live-value id (``HOD33``).

    Args:
        local_id: Local id from the gateway value table.

    Returns:
        Wire register id for device ``AC33`` and kind value.
    """
    return pack_register_id(local_id, device=Device.AC33, kind=ParamKind.VALUE)
