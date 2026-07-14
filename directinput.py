# direct inputs
# source to this solution and code:
# http://stackoverflow.com/questions/14489013/simulate-python-keypresses-for-controlling-a-game
# http://www.gamespp.com/directx/directInputKeyboardScanCodes.html

import sys
import time

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    SendInput = ctypes.windll.user32.SendInput

# Listed are keyboard scan code constants, taken from dinput.h
SCANCODE = {
  "Key_Escape": 1,
  "Key_1": 2,
  "Key_2": 3,
  "Key_3": 4,
  "Key_4": 5,
  "Key_5": 6,
  "Key_6": 7,
  "Key_7": 8,
  "Key_8": 9,
  "Key_9": 10,
  "Key_0": 11,
  "Key_Minus": 12,
  "Key_Equals": 13,
  "Key_Backspace": 14,
  "Key_Tab": 15,
  "Key_Q": 16,
  "Key_W": 17,
  "Key_E": 18,
  "Key_R": 19,
  "Key_T": 20,
  "Key_Y": 21,
  "Key_U": 22,
  "Key_I": 23,
  "Key_O": 24,
  "Key_P": 25,
  "Key_LeftBracket": 26,
  "Key_RightBracket": 27,
  "Key_Enter": 28,
  "Key_LeftControl": 29,
  "Key_A": 30,
  "Key_S": 31,
  "Key_D": 32,
  "Key_F": 33,
  "Key_G": 34,
  "Key_H": 35,
  "Key_J": 36,
  "Key_K": 37,
  "Key_L": 38,
  "Key_SemiColon": 39,
  "Key_Apostrophe": 40,
  "Key_Grave": 41,
  "Key_LeftShift": 42,
  "Key_BackSlash": 43,
  "Key_Z": 44,
  "Key_X": 45,
  "Key_C": 46,
  "Key_V": 47,
  "Key_B": 48,
  "Key_N": 49,
  "Key_M": 50,
  "Key_Comma": 51,
  "Key_Period": 52,
  "Key_Slash": 53,
  "Key_RightShift": 54,
  "Key_Numpad_Multiply": 55,
  "Key_LeftAlt": 56,
  "Key_Space": 57,
  "Key_CapsLock": 58,
  "Key_F1": 59,
  "Key_F2": 60,
  "Key_F3": 61,
  "Key_F4": 62,
  "Key_F5": 63,
  "Key_F6": 64,
  "Key_F7": 65,
  "Key_F8": 66,
  "Key_F9": 67,
  "Key_F10": 68,
  "Key_NumLock": 69,
  "Key_ScrollLock": 70,
  "Key_Numpad_7": 71,
  "Key_Numpad_8": 72,
  "Key_Numpad_9": 73,
  "Key_Numpad_Subtract": 74,
  "Key_Numpad_4": 75,
  "Key_Numpad_5": 76,
  "Key_Numpad_6": 77,
  "Key_Numpad_Add": 78,
  "Key_Numpad_1": 79,
  "Key_Numpad_2": 80,
  "Key_Numpad_3": 81,
  "Key_Numpad_0": 82,
  "Key_Numpad_Decimal": 83,
  "??_84": 84,
  "??_85": 85,
  "??_86_duplicate_Key_BackSlash": 86,
  "Key_F11": 87,
  "Key_F12": 88,
  "??_89": 89,
  "??_90": 90,
  "??_91": 91,
  "??_92": 92,
  "??_93": 93,
  "??_94": 94,
  "??_95": 95,
  "??_96": 96,
  "??_97": 97,
  "??_98": 98,
  "??_99": 99,
  "??_100": 100,
  "??_101": 101,
  "??_102": 102,
  "??_103": 103,
  "??_104": 104,
  "??_105": 105,
  "??_106": 106,
  "??_107": 107,
  "??_108": 108,
  "??_109": 109,
  "??_110": 110,
  "??_111": 111,
  "??_112": 112,
  "??_113": 113,
  "??_114": 114,
  "Key_ABNT_C1": 115,
  "??_116": 116,
  "??_117": 117,
  "??_118": 118,
  "??_119": 119,
  "??_120": 120,
  "??_121": 121,
  "??_122": 122,
  "??_123": 123,
  "??_124": 124,
  "??_125": 125,
  "Key_ABNT_C2": 126,
  "??_127": 127,
  "??_128": 128,
  "??_129": 129,
  "??_130": 130,
  "??_131": 131,
  "??_132": 132,
  "??_133": 133,
  "??_134": 134,
  "??_135": 135,
  "??_136": 136,
  "??_137": 137,
  "??_138": 138,
  "??_139": 139,
  "??_140": 140,
  "??_141": 141,
  "??_142": 142,
  "??_143": 143,
  "Key_PrevTrack": 144,
  "??_145": 145,
  "??_146": 146,
  "??_147": 147,
  "??_148": 148,
  "??_149": 149,
  "??_150": 150,
  "??_151": 151,
  "??_152": 152,
  "Key_NextTrack": 153,
  "??_154": 154,
  "??_155": 155,
  "Key_Numpad_Enter": 156,
  "Key_RightControl": 157,
  "??_158": 158,
  "??_159": 159,
  "Key_Mute": 160,
  "Key_Calculator": 161,
  "Key_PlayPause": 162,
  "??_163": 163,
  "Key_MediaStop": 164,
  "??_165": 165,
  "??_166": 166,
  "??_167": 167,
  "??_168": 168,
  "??_169": 169,
  "??_170": 170,
  "??_171": 171,
  "??_172": 172,
  "??_173": 173,
  "Key_VolumeDown": 174,
  "??_175": 175,
  "Key_VolumeUp": 176,
  "??_177": 177,
  "Key_WebHome": 178,
  "??_179": 179,
  "??_180": 180,
  "Key_Numpad_Divide": 181,
  "??_182": 182,
  "Key_SYSRQ": 183,
  "Key_RightAlt": 184,
  "??_185": 185,
  "??_186": 186,
  "??_187": 187,
  "??_188": 188,
  "??_189": 189,
  "??_190": 190,
  "??_191": 191,
  "??_192": 192,
  "??_193": 193,
  "??_194": 194,
  "??_195": 195,
  "??_196": 196,
  "Key_Pause": 197,
  "??_198": 198,
  "Key_Home": 199,
  "Key_UpArrow": 200,
  "Key_PageUp": 201,
  "??_202": 202,
  "Key_LeftArrow": 203,
  "??_204": 204,
  "Key_RightArrow": 205,
  "??_206": 206,
  "Key_End": 207,
  "Key_DownArrow": 208,
  "Key_PageDown": 209,
  "Key_Insert": 210,
  "Key_Delete": 211,
  "??_212": 212,
  "??_213_possibly_print_screen": 213,
  "??_214": 214,
  "??_215": 215,
  "??_216": 216,
  "??_217": 217,
  "??_218": 218,
  "??_219": 219,
  "??_220": 220,
  "Key_Apps": 221,
  "Key_Power": 222,
  "Key_Sleep": 223,
  "??_224": 224,
  "??_225": 225,
  "??_226": 226,
  "Key_Wake": 227,
  "??_228": 228,
  "Key_WebSearch": 229,
  "Key_WebFavourites": 230,
  "Key_WebRefresh": 231,
  "Key_WebStop": 232,
  "Key_WebForward": 233,
  "Key_WebBack": 234,
  "Key_MyComputer": 235,
  "Key_Mail": 236,
  "Key_MediaSelect": 237,
  "??_238": 238,
  "??_239": 239,
  "??_240": 240,
  "??_241": 241,
  "??_242": 242,
  "??_243": 243,
  "??_244": 244,
  "??_245": 245,
  "??_246": 246,
  "??_247": 247,
  "??_248": 248,
  "??_249": 249,
  "??_250": 250,
  "??_251": 251,
  "??_252": 252,
  "??_253": 253,
  "??_254": 254
}


# ===========================================================================
# Linux backend: evdev/uinput virtual keyboard
#
# DirectInput scancodes (dinput.h / AT set 1) are identical to Linux input
# keycodes for the entire main keyboard block (0x01..0x58). Extended
# (0xE0-prefixed) keys differ and are remapped below. Wine/Proton converts
# evdev keycodes back into the same DIK scancodes in-game, so injecting at
# the uinput layer is exact — no XTEST, no layout dependency for bindings.
# ===========================================================================

if not _IS_WINDOWS:
    import atexit
    from evdev import UInput, ecodes as e

    # DIK (extended) -> Linux input keycode
    _DIK_TO_LINUX_EXT = {
        144: e.KEY_PREVIOUSSONG,   # Key_PrevTrack
        153: e.KEY_NEXTSONG,       # Key_NextTrack
        156: e.KEY_KPENTER,        # Key_Numpad_Enter
        157: e.KEY_RIGHTCTRL,      # Key_RightControl
        160: e.KEY_MUTE,           # Key_Mute
        161: e.KEY_CALC,           # Key_Calculator
        162: e.KEY_PLAYPAUSE,      # Key_PlayPause
        164: e.KEY_STOPCD,         # Key_MediaStop
        174: e.KEY_VOLUMEDOWN,     # Key_VolumeDown
        176: e.KEY_VOLUMEUP,       # Key_VolumeUp
        178: e.KEY_HOMEPAGE,       # Key_WebHome
        181: e.KEY_KPSLASH,        # Key_Numpad_Divide
        183: e.KEY_SYSRQ,          # Key_SYSRQ
        184: e.KEY_RIGHTALT,       # Key_RightAlt
        197: e.KEY_PAUSE,          # Key_Pause
        199: e.KEY_HOME,           # Key_Home
        200: e.KEY_UP,             # Key_UpArrow
        201: e.KEY_PAGEUP,         # Key_PageUp
        203: e.KEY_LEFT,           # Key_LeftArrow
        205: e.KEY_RIGHT,          # Key_RightArrow
        207: e.KEY_END,            # Key_End
        208: e.KEY_DOWN,           # Key_DownArrow
        209: e.KEY_PAGEDOWN,       # Key_PageDown
        210: e.KEY_INSERT,         # Key_Insert
        211: e.KEY_DELETE,         # Key_Delete
        219: e.KEY_LEFTMETA,       # Key_LeftWin
        220: e.KEY_RIGHTMETA,      # Key_RightWin
        221: e.KEY_COMPOSE,        # Key_Apps
        222: e.KEY_POWER,          # Key_Power
        223: e.KEY_SLEEP,          # Key_Sleep
        227: e.KEY_WAKEUP,         # Key_Wake
    }

    def _dik_to_linux(code: int) -> int | None:
        if 1 <= code <= 0x58:          # main block: identity
            return code
        return _DIK_TO_LINUX_EXT.get(code)

    _uinput = None

    def _get_uinput():
        global _uinput
        if _uinput is None:
            keys = set(range(1, 0x59)) | set(_DIK_TO_LINUX_EXT.values())
            try:
                _uinput = UInput({e.EV_KEY: sorted(keys)}, name="edap-virtual-kbd")
            except PermissionError as ex:
                raise PermissionError(
                    "Cannot open /dev/uinput. Install the udev rule "
                    "(see setup-linux.sh) and ensure you are in the "
                    "'input' group, then re-login."
                ) from ex
            atexit.register(_uinput.close)
            time.sleep(0.5)  # let libinput/compositor pick up the new device
        return _uinput

    def _emit(dik_code: int, value: int):
        kc = _dik_to_linux(dik_code)
        if kc is None:
            return
        ui = _get_uinput()
        ui.write(e.EV_KEY, kc, value)
        ui.syn()

    def PressKey(hexKeyCode):
        _emit(hexKeyCode, 1)

    def ReleaseKey(hexKeyCode):
        _emit(hexKeyCode, 0)


# C struct redefinitions (Windows only)

if _IS_WINDOWS:
    PUL = ctypes.POINTER(ctypes.c_ulong)
    class KeyBdInput(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", PUL)]

    class HardwareInput(ctypes.Structure):
        _fields_ = [("uMsg", ctypes.c_ulong),
                    ("wParamL", ctypes.c_short),
                    ("wParamH", ctypes.c_ushort)]

    class MouseInput(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long),
                    ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong),
                    ("time",ctypes.c_ulong),
                    ("dwExtraInfo", PUL)]

    class Input_I(ctypes.Union):
        _fields_ = [("ki", KeyBdInput),
                     ("mi", MouseInput),
                     ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong),
                    ("ii", Input_I)]


    # Actual Functions

    def PressKey(hexKeyCode):
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

    def ReleaseKey(hexKeyCode):
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
