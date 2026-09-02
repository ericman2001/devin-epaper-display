#!/usr/bin/env python3
"""Generator for the ESP32-C6-WROOM-1 e-paper display KiCad 8 schematic.

Connectivity is expressed entirely with *global labels* (which merge by name
across the whole sheet), so the exported netlist is correct regardless of the
exact placement of the symbols.  Each device pin gets a short wire stub ending
in a global label carrying that pin's net name.

Run:  python3 gen_sch.py   ->  writes epaper-display.kicad_sch
Then validate with: kicad-cli sch export netlist ...
"""
import uuid
import os

SCH = "epaper-display.kicad_sch"

# ----------------------------------------------------------------------------
# Deterministic UUIDs.  Every uuid emitted below is a UUIDv5 hash of a stable
# key string (reference designator + pin, mostly) rather than a random uuid4.
#
# This matters as soon as a .kicad_pcb exists: KiCad links each footprint to its
# schematic symbol by the symbol's UUID, so a fresh random uuid on every run
# would orphan every footprint on the board each time this script is re-run
# (recoverable only via "re-link footprints by reference designator").  It also
# keeps `git diff` empty when nothing actually changed.
#
# Every key must be unique -- two call sites sharing a key would emit the same
# uuid twice and KiCad rejects a schematic with duplicate uuids, so U() raises.
UUID_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "epaper-display.kicad")
_uuid_keys = set()

def U(key):
    """Stable UUID for `key`.  Raises if `key` has already been used."""
    if key in _uuid_keys:
        raise SystemExit(f"duplicate UUID key: {key!r}")
    _uuid_keys.add(key)
    return str(uuid.uuid5(UUID_NS, key))

ROOT_UUID = U("sheet:root")

# ----------------------------------------------------------------------------
# Symbol library entries.  Every symbol is a rectangle with pins auto-laid out
# on the left and right edges.  Pin (at) coordinate is the *tip* (connection
# point); the graphic extends back into the body by `length`.
# ----------------------------------------------------------------------------
GRID = 2.54
PIN_LEN = 2.54

class SymDef:
    def __init__(self, libname, pins, add_power_flags=False):
        # pins: list of (number, name, etype)
        self.libname = libname
        self.pins = pins
        # split pins left/right
        n = len(pins)
        half = (n + 1) // 2
        self.left = pins[:half]
        self.right = pins[half:]
        rows = max(len(self.left), len(self.right))
        self.height = (rows + 1) * GRID
        self.width = 4 * GRID
        # compute pin geometry (library coords, +Y up)
        self.pin_geom = {}  # number -> (x, y, angle, side)
        top = self.height / 2
        for i, (num, name, et) in enumerate(self.left):
            y = top - (i + 1) * GRID
            x = -self.width / 2 - PIN_LEN
            self.pin_geom[num] = (x, y, 0, 'L')   # angle 0 => points right(into body from left tip)
        for i, (num, name, et) in enumerate(self.right):
            y = top - (i + 1) * GRID
            x = self.width / 2 + PIN_LEN
            self.pin_geom[num] = (x, y, 180, 'R')

    def lib_sexpr(self, prefix="epaper:", indent="    "):
        s = []
        s.append(f'{indent}(symbol "{prefix}{self.libname}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)')
        s.append(f'      (property "Reference" "U" (at 0 {self.height/2+2.54:.3f} 0)')
        s.append(f'        (effects (font (size 1.27 1.27))))')
        s.append(f'      (property "Value" "{self.libname}" (at 0 {-self.height/2-2.54:.3f} 0)')
        s.append(f'        (effects (font (size 1.27 1.27))))')
        s.append(f'      (property "Footprint" "" (at 0 0 0)')
        s.append(f'        (effects (font (size 1.27 1.27)) hide))')
        s.append(f'      (property "Datasheet" "" (at 0 0 0)')
        s.append(f'        (effects (font (size 1.27 1.27)) hide))')
        # body rectangle
        s.append(f'      (symbol "{self.libname}_0_1"')
        s.append(f'        (rectangle (start {-self.width/2:.3f} {self.height/2:.3f}) (end {self.width/2:.3f} {-self.height/2:.3f})')
        s.append(f'          (stroke (width 0.254) (type default)) (fill (type background))))')
        # pins
        s.append(f'      (symbol "{self.libname}_1_1"')
        for num, name, et in self.pins:
            x, y, ang, side = self.pin_geom[num]
            safe = name.replace('"', "")
            s.append(f'        (pin {et} line (at {x:.3f} {y:.3f} {ang}) (length {PIN_LEN})')
            s.append(f'          (name "{safe}" (effects (font (size 1.016 1.016))))')
            s.append(f'          (number "{num}" (effects (font (size 1.016 1.016)))))')
        s.append('      )')
        s.append('    )')
        return "\n".join(s)


# ----------------------------------------------------------------------------
# Device catalogue
# ----------------------------------------------------------------------------
symdefs = {}

def mk(libname, pins):
    symdefs[libname] = SymDef(libname, pins)
    return libname

# ESP32-C6-WROOM-1 module (29 pins).  Pin numbers and names are Table 3-1 of
# components/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf (v1.4, p.11), which is
# a 14 + 14 castellation layout plus the bottom thermal pad on pin 29.
#
# Note pin 22 is a real NC pin on this module (GPIO14 is not bonded out of the
# package on non-SiP-flash variants), and that RXD0/TXD0 on pins 24/25 are
# GPIO17/GPIO16 -- the names are the UART0 IO MUX function, not the GPIO number.
MODULE_PINS = [
    (1,"GND","power_in"),(2,"3V3","power_in"),(3,"EN","input"),
    (4,"IO4","bidirectional"),(5,"IO5","bidirectional"),(6,"IO6","bidirectional"),
    (7,"IO7","bidirectional"),(8,"IO0","bidirectional"),(9,"IO1","bidirectional"),
    (10,"IO8","bidirectional"),(11,"IO10","bidirectional"),(12,"IO11","bidirectional"),
    (13,"IO12","bidirectional"),(14,"IO13","bidirectional"),(15,"IO9","bidirectional"),
    (16,"IO18","bidirectional"),(17,"IO19","bidirectional"),(18,"IO20","bidirectional"),
    (19,"IO21","bidirectional"),(20,"IO22","bidirectional"),(21,"IO23","bidirectional"),
    (22,"NC","no_connect"),(23,"IO15","bidirectional"),(24,"RXD0","bidirectional"),
    (25,"TXD0","bidirectional"),(26,"IO3","bidirectional"),(27,"IO2","bidirectional"),
    (28,"GND","power_in"),(29,"EPAD","power_in"),
]
mk("ESP32-C6-WROOM-1", MODULE_PINS)

# E-paper 24-pin FPC breakout
EPD_PINS = [
    (1,"NC","no_connect"),(2,"GDR","output"),(3,"RESE","input"),(4,"NC","no_connect"),
    (5,"VSH2","passive"),(6,"TSCL","output"),(7,"TSDA","bidirectional"),(8,"BS1","input"),
    (9,"BUSY","output"),(10,"RES#","input"),(11,"D/C#","input"),(12,"CS#","input"),
    (13,"SCL","input"),(14,"SDA","input"),(15,"VDDIO","power_in"),(16,"VCI","power_in"),
    # VPP is the panel's OTP *programming* pin.  It is not a supply rail and is
    # never driven in normal operation (it sits on EPD_VPP with only R23), so it
    # is passive, not power_in -- as power_in it raised a spurious
    # power_pin_not_driven ERC error.
    (17,"VSS","power_in"),(18,"VDD","passive"),(19,"VPP","passive"),(20,"VSH1","passive"),
    (21,"VGH","passive"),(22,"VSL","passive"),(23,"VGL","passive"),(24,"VCOM","passive"),
    # The Hirose FH12 footprint carries two mechanical hold-down tabs, both pads
    # named "MP".  They are not display signals, but they must exist as a symbol
    # pin or they stay floating on the board (no error -- KiCad silently leaves
    # unmatched footprint pads unconnected).  Tie them to GND: that is what gives
    # the connector its solder retention against FPC insertion force.
    ("MP","MP","passive"),
]
mk("EPD_AES200200A00", EPD_PINS)

# USB-C receptacle, USB 2.0 16-pin.  Pin *numbers* are the real A/B pad names so
# they map 1:1 onto Connector_USB:USB_C_Receptacle_GCT_USB4085 (pads A1 A4 A5 A6
# A7 A8 A9 A12 / B1 B4 B5 B6 B7 B8 B9 B12 + four shield pads all numbered SH).
# NB: the shield pads are "SH" in the KiCad footprint libs, not the "S1" used by
# KiCad's own USB-C *symbol* -- using S1 here makes the PCB update fail with
# "pad S1 not found in Connector_USB:USB_C_Receptacle_GCT_USB4085".
# The duplicated rows MUST be paralleled in the netlist below or the cable only
# works in one orientation.
mk("USB_C_Receptacle_USB2.0", [
    ("A1","GND","power_in"),("A4","VBUS","power_in"),("A5","CC1","passive"),
    ("A6","D+","bidirectional"),("A7","D-","bidirectional"),("A8","SBU1","passive"),
    ("A9","VBUS","power_in"),("A12","GND","power_in"),
    ("B1","GND","power_in"),("B4","VBUS","power_in"),("B5","CC2","passive"),
    ("B6","D+","bidirectional"),("B7","D-","bidirectional"),("B8","SBU2","passive"),
    ("B9","VBUS","power_in"),("B12","GND","power_in"),
    ("SH","SHIELD","passive"),
])

# MCP73831 SOT-23-5
mk("MCP73831", [
    (1,"STAT","open_collector"),(2,"VSS","power_in"),(3,"VBAT","power_out"),
    (4,"VDD","power_in"),(5,"PROG","passive"),
])

# Fixed 3.3V LDO in SOT-23-5.  This pinout (1=IN 2=GND 3=EN 4=NC 5=OUT) is the
# de-facto standard for the package and is shared by every candidate part
# considered here -- TLV75733PDBVR, AP2112K-3.3, XC6220B331MR and
# TPS7A0533PDBV all drop into these pads unchanged, so the regulator can be
# re-specced later without touching the schematic.  Verified against the
# KiCad 8.0.9 Regulator_Linear symbol library.
mk("LDO_SOT23_5", [
    (1,"IN","power_in"),(2,"GND","power_in"),(3,"EN","input"),
    (4,"NC","no_connect"),(5,"OUT","power_out"),
])

# N-channel MOSFET SOT-23 (G,S,D)
mk("MOSFET_N", [ (1,"G","input"),(2,"S","passive"),(3,"D","passive") ])

# DW01A 1S Li-ion protection controller, SOT-23-6.  Pinout from the datasheet
# "引脚排列 / Pinning" table (p.2) and independently confirmed against KiCad
# 8.0.9's Battery_Management:DW01A symbol, which uses the alternate names
# OD/CS/OC/TD/VCC/GND for the same six pins in the same order.
mk("DW01A", [
    (1,"DO","output"),(2,"VM","input"),(3,"CO","output"),
    (4,"NC","no_connect"),(5,"VDD","power_in"),(6,"VSS","power_in"),
])

# FS8205A dual N-channel MOSFET, SOT-23-6, common drain.
#
# Pinout taken from the "Package and Pin Configuration" drawing in
# components/fs8205a-techpublic.pdf, which is the only source of the two
# FS8205A datasheets here that links function to package position:
#
#       pin 6  G1      pin 5  D1/D2    pin 4  G2
#       pin 1  S1      pin 2  D1/D2    pin 3  S2
#
# i.e. each half occupies one END of the package (FET1 = S1/G1 at pins 1/6,
# FET2 = S2/G2 at pins 3/4) with the common drain brought out on the two MIDDLE
# pins.  That is a symmetric leadframe layout and it is what the drawing shows.
#
# Note this is NOT the commonly-quoted "8205A" mapping (1=S1 2=G1 3=S2 4=G2
# 5=D2 6=D1), which puts a gate in the middle of the source row.  An earlier
# revision of this file wired that version; it was wrong.  Under it, PROT_DO
# would have been driven into a drain and G1 tied to the drain node, and the
# protection would have silently not worked.
#
# Cheap confirmation on the bench, worth doing once: the two pins shorted to
# each other are the drains; in diode mode, red probe on a pin and black on the
# drain node reading ~0.5-0.7 V identifies a SOURCE (body diode source->drain);
# the remaining two pins are the gates.
mk("FS8205A", [
    (1,"S1","passive"),(2,"D1/D2","passive"),(3,"S2","passive"),
    (4,"G2","input"),(5,"D1/D2","passive"),(6,"G1","input"),
])


# generic 2-pin passives
mk("R", [ (1,"1","passive"),(2,"2","passive") ])
mk("C", [ (1,"1","passive"),(2,"2","passive") ])
mk("L", [ (1,"1","passive"),(2,"2","passive") ])
mk("D_Schottky", [ (1,"A","passive"),(2,"K","passive") ])
mk("D_TVS", [ (1,"A","passive"),(2,"K","passive") ])
mk("LED", [ (1,"A","passive"),(2,"K","passive") ])
mk("SW_PUSH", [ (1,"1","passive"),(2,"2","passive") ])
mk("Conn_JST_PH_2", [ (1,"1","passive"),(2,"2","passive") ])
# USBLC6-2SC6 ESD TVS, SOT-23-6 real pinout: 1=I/O1 2=GND 3=I/O2 4=I/O2 5=VBUS 6=I/O1
mk("USBLC6_ESD", [
    (1,"IO1","passive"),(2,"GND","power_in"),(3,"IO2","passive"),
    (4,"IO2","passive"),(5,"VBUS","power_in"),(6,"IO1","passive"),
])

# generic headers
mk("Conn_1x04", [ (i+1, str(i+1), "passive") for i in range(4) ])
mk("Conn_2x04", [ (i+1, str(i+1), "passive") for i in range(8) ])

# power flag (marks a net as driven, for ERC)
mk("PWR_FLAG", [ (1, "pwr", "power_out") ])


# ----------------------------------------------------------------------------
# Component instances.  Each: (ref, value, libname, {pin_number: net_name},
#                              footprint_text)
# ----------------------------------------------------------------------------
NC = None  # marks a no-connect

# default footprints for the generic passive symbols.  0805 throughout: this is
# a hand-soldered board (see README), and 0805 is the smallest chip package that
# is comfortable with a fine-tip iron.
FP_R = "Resistor_SMD:R_0805_2012Metric"
FP_C = "Capacitor_SMD:C_0805_2012Metric"
FP_C_1206 = "Capacitor_SMD:C_1206_3216Metric"   # bulk electrolytic-class ceramics
FP_D_SOD123 = "Diode_SMD:D_SOD-123"
FP_D_SMA = "Diode_SMD:D_SMA"
# wire-wound shielded power inductor land pattern (4.0 x 4.0 mm).  The panel
# datasheet's CDRH2D18 has no KiCad footprint; MWSA0402S is the same class of
# part, is stocked, and has two big end pads that hand-solder easily.
FP_L_MWSA0402S = "Inductor_SMD:L_Sunlord_MWSA0402S"
# every tactile push button is the same FSJM-series 6x6mm 4-pin through-hole
# part (Omron/Alps 6.5mm x 4.5mm pad pitch), which this footprint models.
FP_SW_6MM = "Button_Switch_THT:SW_PUSH_6mm"

instances = []
def add(ref, value, lib, nets, fp="", dnp=False, in_bom=True):
    instances.append(dict(ref=ref, value=value, lib=lib, nets=nets, fp=fp, dnp=dnp, in_bom=in_bom))

# --- ESP32-C6-WROOM-1 ---
# GPIO allocation.  The C6 brings out 23 usable GPIOs where the S3 module gave
# 36, and -- worse for this board -- three separate scarce resources all live in
# the same GPIO0-GPIO7 block, so the allocation is far more forced than the S3's
# was.  Nothing here is arbitrary; every pin below is the only one left that can
# do its job:
#
#   * Deep-sleep wake is GPIO0-GPIO7 and nothing else.  The C6 has eight LP
#     (RTC) IOs, SOC_RTCIO_PIN_COUNT = 8, and EXT1 can only be armed on those.
#     A board that is asleep 99.98 % of the time needs all six buttons to wake
#     it, so six of those eight pins are spoken for before anything else.
#   * ADC1 is GPIO0-GPIO6 (ADC1_CH0..CH6).  There is no ADC2 on the C6 at all,
#     which is a real *improvement* -- the S3's "ADC2 is unusable while Wi-Fi is
#     on" trap simply does not exist here -- but it puts every analog-capable
#     pin inside the same block the buttons need.
#   * SPI2's IO MUX pins are GPIO2 (FSPIQ), GPIO4 (FSPIHD), GPIO5 (FSPIWP),
#     GPIO6 (FSPICLK), GPIO7 (FSPID) and GPIO16 (FSPICS0) -- the same block
#     again, plus UART0's TX pin.
#
# Six buttons plus VBAT_SENSE fill seven of the eight LP pins.  GPIO7 is the one
# LP pin with no ADC channel (datasheet Table 3-1: IO7 lists no ADC1_CHn), so a
# button takes it and the leftover LP pin is GPIO1 = ADC1_CH1.  That single pin
# goes to the expansion header, where it is both the only analog input and the
# only interrupt line that can wake the board.
#
# The panel and USB then take pins that can do nothing else: GPIO18-GPIO23 for
# the six panel signals and GPIO12/GPIO13 for USB, which the USB Serial/JTAG PHY
# fixes in hardware.  Panel SPI therefore runs through the GPIO matrix rather
# than the SPI2 IO MUX; that costs nothing, because the matrix supports 40 MHz
# and an SSD1681 panel is clocked at a few MHz.
#
# See README 7.  Pin comments below are module pin -> GPIO where they differ.
add("U1", "ESP32-C6-WROOM-1-N8", "ESP32-C6-WROOM-1", {
    1:"GND", 2:"+3V3", 3:"EN",
    # IO4-IO7 = MTMS / MTDI / MTCK / MTDO, i.e. the external JTAG pads.  They
    # are buttons here; debug goes over USB Serial/JTAG instead (see R15).
    4:"BTN_UP", 5:"BTN_DOWN", 6:"BTN_LEFT", 7:"BTN_RIGHT",
    8:"VBAT_SENSE",                 # IO0   ADC1_CH0 / LP_GPIO0
    9:"EXP_ADC_IRQ",                # IO1   ADC1_CH1 / LP_GPIO1 (EXT1 wake)
    10:"EXP_IO8",                   # IO8   boot-mode strap -- R28 pull-up
    11:"EXP_SDA", 12:"EXP_SCL",     # IO10 / IO11
    13:"USB_DM_MCU", 14:"USB_DP_MCU",   # IO12 / IO13, fixed by the USB PHY
    15:"BOOT",                      # IO9   download-boot strap
    16:"EPD_BUSY", 17:"EPD_RST",    # IO18 / IO19
    18:"EPD_DC", 19:"EPD_CS",       # IO20 / IO21
    20:"EPD_MOSI", 21:"EPD_SCLK",   # IO22 / IO23
    22:NC,                          # module NC pin (GPIO14 is not bonded out)
    23:"STRAP_IO15",                # IO15  JTAG-source strap -- R15 pull-up
    24:"UART_RXD0", 25:"UART_TXD0", # IO17 / IO16
    26:"BTN_SELECT",                # IO3   ADC1_CH3 / LP_GPIO3
    27:"BTN_CANCEL",                # IO2   ADC1_CH2 / LP_GPIO2
    28:"GND", 29:"GND",
}, fp="Espressif:ESP32-C6-WROOM-1")

# --- E-paper FPC breakout ---
add("J1", "AES200200A00 FPC", "EPD_AES200200A00", {
    1:NC, 2:"EPD_GDR", 3:"EPD_RESE", 4:NC, 5:"EPD_VSH2",
    6:"EPD_TSCL", 7:"EPD_TSDA", 8:"GND", 9:"EPD_BUSY", 10:"EPD_RST",
    11:"EPD_DC", 12:"EPD_CS", 13:"EPD_SCLK", 14:"EPD_MOSI",
    15:"+3V3", 16:"+3V3", 17:"GND", 18:"EPD_VDD", 19:"EPD_VPP",
    20:"EPD_VSH1", 21:"EPD_VGH", 22:"EPD_VSL", 23:"EPD_VGL", 24:"EPD_VCOM",
    "MP":"GND",
}, fp="Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal")

# --- USB-C receptacle ---
# Both rows are paralleled (A4/B4/A9/B9 = VBUS, A1/B1/A12/B12 = GND, A6/B6 = D+,
# A7/B7 = D-) so the receptacle works in either cable orientation.  CC1 (A5) and
# CC2 (B5) each get their own 5.1k Rd and must NOT be shorted together.
add("J2", "USB-C 2.0 receptacle", "USB_C_Receptacle_USB2.0", {
    "A1":"GND",  "A4":"VBUS", "A5":"CC1", "A6":"USB_DP", "A7":"USB_DM",
    "A8":NC,     "A9":"VBUS", "A12":"GND",
    "B1":"GND",  "B4":"VBUS", "B5":"CC2", "B6":"USB_DP", "B7":"USB_DM",
    "B8":NC,     "B9":"VBUS", "B12":"GND",
    "SH":"GND",
}, fp="Connector_USB:USB_C_Receptacle_GCT_USB4085")
add("R1", "5.1k", "R", {1:"CC1", 2:"GND"}, fp=FP_R)
add("R2", "5.1k", "R", {1:"CC2", 2:"GND"}, fp=FP_R)
# 0 ohm, not 22 ohm: the ESP32-C6 USB PHY already contains its series
# termination, so an extra 22 ohm per leg would add 44 ohm differential to a
# 90 ohm pair and squash the full-speed eye.  Keep the pads as tuning stubs.
add("R3", "0", "R", {1:"USB_DP", 2:"USB_DP_MCU"}, fp=FP_R)
add("R4", "0", "R", {1:"USB_DM", 2:"USB_DM_MCU"}, fp=FP_R)
add("D1", "USBLC6-2SC6", "USBLC6_ESD",
    {1:"USB_DP", 2:"GND", 3:"USB_DM", 4:"USB_DM", 5:"VBUS", 6:"USB_DP"},
    fp="Package_TO_SOT_SMD:SOT-23-6")
# MCP73831 DS20001984H 6.1.1.2: input overvoltage protection "must be used when
# the input power source is hot-pluggable.  This includes USB cables."
add("D7", "SMAJ5.0A", "D_TVS", {1:"GND", 2:"VBUS"}, fp=FP_D_SMA)

# --- MCP73831 charger ---
add("U2", "MCP73831T-2ACI/OT", "MCP73831", {
    1:"CHG_STAT", 2:"GND", 3:"VBAT", 4:"VBUS", 5:"CHG_PROG",
}, fp="Package_TO_SOT_SMD:SOT-23-5")
add("R5", "10k", "R", {1:"CHG_PROG", 2:"GND"}, fp=FP_R)  # I_chg = 1000/10k = 100 mA
# RLED returns to VBUS, NOT to +3V3.  This mirrors the datasheet application
# circuit (Fig 6-1, RLED from VDD to STAT).  Referencing it to the regulated
# rail would forward-bias the LED from the battery into the STAT pin whenever
# USB is absent, back-feeding the charger's VDD node and the USB-C VBUS contact
# and violating the "all I/O <= VDD + 0.3 V" absolute maximum.
add("R6", "1k", "R", {1:"VBUS", 2:"CHG_LED"}, fp=FP_R)
add("D2", "LED (charge)", "LED", {1:"CHG_LED", 2:"CHG_STAT"},
    fp="LED_THT:LED_D3.0mm")
add("C1", "4.7uF", "C", {1:"VBUS", 2:"GND"}, fp=FP_C)   # charger input
add("C2", "4.7uF", "C", {1:"VBAT", 2:"GND"}, fp=FP_C)   # charger output
# --- Battery connector and on-board 1S protection (DW01A + FS8205A) ---
#
# J3 is now the raw *cell*, not a protected pack: pin 1 is B+ (which is also P+,
# since the high side is never switched) and pin 2 is B- on its own net.  The
# back-to-back FETs sit in the low side between B- and board GND, exactly as the
# DW01A datasheet application circuit (p.9) draws it.
#
# This replaces the previous "buy a cell with a protection PCM" requirement.
# The target cell is a Turnigy BoltX LiHV whoop pack, which like all drone packs
# is a bare cell -- so the protection has to live here.
add("J3", "LiPo cell (B+/B-)", "Conn_JST_PH_2", {1:"VBAT", 2:"BATT_NEG"},
    fp="Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal")
add("U4", "DW01A", "DW01A", {
    1:"PROT_DO", 2:"PROT_VM", 3:"PROT_CO", 4:NC, 5:"PROT_VDD", 6:"BATT_NEG",
}, fp="Package_TO_SOT_SMD:SOT-23-6")
# Q2 half 1 = discharge control (gate DO, source B-); half 2 = charge control
# (gate CO, source P-/GND).  That pairing is set by the DW01A: it turns the
# discharge FET off by driving DO to VSS and the charge FET off by driving CO to
# VM, so each gate must be referenced to its own source (datasheet p.6).
add("Q2", "FS8205A", "FS8205A", {
    1:"BATT_NEG", 2:"PROT_MID", 3:"GND", 4:"PROT_CO", 5:"PROT_MID", 6:"PROT_DO",
}, fp="Package_TO_SOT_SMD:SOT-23-6")
# R1/C1/R2 of the datasheet application circuit.  100 ohm is the value the
# datasheet both draws and uses as the test condition for the overcharge-restore
# threshold, so do not change it casually.
add("R24", "100", "R", {1:"VBAT", 2:"PROT_VDD"}, fp=FP_R)
add("C21", "100nF", "C", {1:"PROT_VDD", 2:"BATT_NEG"}, fp=FP_C)
add("R25", "1k", "R", {1:"PROT_VM", 2:"GND"}, fp=FP_R)
#
# D6 (the SS14 reverse-polarity crowbar) has been REMOVED, deliberately.  Its
# whole rationale was "short a reversed cell and let the pack's PCM interrupt
# the fault".  With the protection moved on-board it sits *downstream* of a
# reversed connector, so there is no longer anything upstream to clear the
# fault -- and an 80C 300 mAh cell can source ~24 A into a 1 A diode.  Leaving
# it in would make the board's designated short-circuit path a fire risk rather
# than a safeguard.  Reverse polarity is now handled by the keyed connector plus
# the documented meter check; see README 4 for the residual risk this leaves.

# --- 3.3V LDO ---
# TLV75733PDBVR: 1 A, Iq ~25 uA, SOT-23-5.  Replaces an MCP1825S-3302, whose
# 120 uA typ / 220 uA max quiescent current was ~15x the ESP32-S3's own
# deep-sleep draw and dominated the standby budget outright.  On a board that
# is asleep 99.98 % of the time, Iq is the only regulator figure of merit that
# moves the battery life needle -- see README 2 for why this stayed linear
# rather than becoming a switcher.
#
# EN is tied to IN so the rail is always on; it must not be left floating.
add("U3", "TLV75733PDBVR", "LDO_SOT23_5", {
    1:"VBAT", 2:"GND", 3:"VBAT", 4:NC, 5:"+3V3",
}, fp="Package_TO_SOT_SMD:SOT-23-5")
add("C3", "4.7uF", "C", {1:"VBAT", 2:"GND"}, fp=FP_C)   # LDO input  (>=1uF, X7R)
add("C4", "4.7uF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)   # LDO output (>=1uF, X7R, ESR<1ohm)
# --- Rail buffering ---
# The module datasheet lists IVDD >= 0.5 A as a recommended operating condition,
# so an 802.11b TX burst (355 mA peak) landing on top of a panel refresh needs
# somewhere to come from.  U3 is rated at 1 A with a 1.2 A minimum current limit
# (TLV757P 5.5), which is real headroom rather than exactly-500 mA.
#
# The bulk sits on the *output*, where the load transient actually is.  An
# earlier revision was forced to put it on VBAT instead because the MCP1825S
# capped COUT at 22 uF; TLV757P 7.1.1 allows "no greater than 200uF", so that
# constraint is gone.  +3V3 now carries C4 4.7 + C6 10 + C12 1 + C5 0.1 +
# C18 47 = 62.8 uF nominal, ~31 uF after the 50 % ceramic derating the same
# section tells us to assume -- comfortably inside 200 uF.
add("C18", "47uF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C_1206)
# Input-side bulk (7.1.1 asks for >= 1 uF; more helps a high-impedance source
# and large fast load steps).  This is also the node a solar / supercap front
# end would attach to.
add("C20", "100uF", "C", {1:"VBAT", 2:"GND"}, fp=FP_C_1206)

# --- MCU support ---
add("C5", "100nF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)
add("C6", "10uF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)
add("R7", "10k", "R", {1:"+3V3", 2:"EN"}, fp=FP_R)
add("C7", "1uF", "C", {1:"EN", 2:"GND"}, fp=FP_C)
add("SW1", "EN/RESET", "SW_PUSH", {1:"EN", 2:"GND"}, fp=FP_SW_6MM)
add("R8", "10k", "R", {1:"+3V3", 2:"BOOT"}, fp=FP_R)
add("SW2", "BOOT", "SW_PUSH", {1:"BOOT", 2:"GND"}, fp=FP_SW_6MM)

# --- User buttons: D-pad + select + cancel ---
# GPIO4 (up), 5 (down), 6 (left), 7 (right), 3 (select), 2 (cancel).  Active-low
# to GND.  These six occupy GPIO2-GPIO7, which is six of the C6's eight LP
# (RTC) IOs -- the complete set of pins EXT1 can wake the chip from.  See the
# allocation note on U1: on this part that is not a preference, it is the only
# arrangement that lets every button wake the board.
#
# They get *external* pull-ups because the digital-domain internal pull-ups drop
# out in deep sleep, and an EXT1 wake source that floats produces phantom wakes
# that quietly eat the battery.  100k (not 10k) keeps the held-button current to
# 33 uA.
#
# Side effect worth knowing about: GPIO4 (MTMS) and GPIO5 (MTDI) are also
# strapping pins, for the SDIO slave sampling/driving clock edge (module
# datasheet Table 4-4).  R17/R18 latch both to 1 at reset -- unless that button
# happens to be held down -- which selects "rising edge sampling, rising edge
# output".  This board never uses the SDIO slave interface, so the setting is
# inert either way; it is recorded here so nobody rediscovers it as a mystery.
BUTTONS = [("SW3","BTN_UP"), ("SW4","BTN_DOWN"), ("SW5","BTN_LEFT"),
           ("SW6","BTN_RIGHT"), ("SW7","BTN_SELECT"), ("SW8","BTN_CANCEL")]
for _i, (_sw, _net) in enumerate(BUTTONS):
    add(_sw, _net, "SW_PUSH", {1:_net, 2:"GND"}, fp=FP_SW_6MM)
    add(f"R{17+_i}", "100k", "R", {1:"+3V3", 2:_net}, fp=FP_R)
# 100k rather than 10k: these only ever fight a CMOS input's leakage, and 10k
# would burn 330 uA whenever firmware drives the pin against the resistor.
add("R14", "100k", "R", {1:"+3V3", 2:"EPD_CS"}, fp=FP_R)
# Populated, NOT DNP.  Module datasheet 4.4: GPIO15 "does not have any internal
# pull resistors and the strapping value must be controlled by the external
# circuit that cannot be in a high impedance state."
#
# Pull-UP, where the S3 revision of this board pulled its equivalent strap
# (GPIO3) down.  The direction is not cosmetic: datasheet Table 4-7 says that
# once EFUSE_JTAG_SEL_ENABLE is burnt, GPIO15 = 1 keeps JTAG on the USB
# Serial/JTAG controller and GPIO15 = 0 moves it to the MTDI/MTCK/MTMS/MTDO
# pads.  Those pads are GPIO4-GPIO7 on the C6, which this board wires to four
# of the six buttons, so pad-JTAG is not reachable here -- pulling the strap low
# would trade a working debug port for an unusable one.  With default (unburnt)
# eFuses GPIO15 is ignored and USB Serial/JTAG is used regardless; R15 is what
# keeps that true afterwards, and what stops the pin floating meanwhile.
add("R15", "10k", "R", {1:"+3V3", 2:"STRAP_IO15"}, fp=FP_R)
add("R16", "100k", "R", {1:"EPD_RST", 2:"GND"}, fp=FP_R)

# --- Battery sense divider (into ADC1_CH0 / GPIO0) ---
# 1M/1M, not 100k/100k: the divider is across the cell permanently, and at 100k
# it drew 21 uA -- three times the ESP32-C6's own 7 uA deep-sleep current
# (module datasheet Table 6-8) on a device whose entire premise is deep sleep.
# 1M brings that to 2.1 uA.
# C8 is the ADC's charge reservoir, which is what makes the now-500k source
# impedance acceptable to the SAR; allow ~250 ms of settling after wake and
# average several samples.
add("R9", "1M", "R", {1:"VBAT", 2:"VBAT_SENSE"}, fp=FP_R)
add("R10", "1M", "R", {1:"VBAT_SENSE", 2:"GND"}, fp=FP_R)
add("C8", "100nF", "C", {1:"VBAT_SENSE", 2:"GND"}, fp=FP_C)

# --- E-paper DC/DC boost + charge pump (reference circuit, datasheet p.24) ---
# 47 uH / Io >= 500 mA per the panel datasheet reference table.  Sunlord
# MWSA0402S-470MT or Sumida CDRH2D18-470 -- confirm Isat >= 500 mA at order
# time, the 4x4mm size class sits right around that rating.
add("L1", "47uH", "L", {1:"EPD_SW", 2:"+3V3"}, fp=FP_L_MWSA0402S)   # VCI = +3V3
add("Q1", "Si1304BDL / NX3008NBK", "MOSFET_N",
    {1:"EPD_GDR", 2:"EPD_RESE", 3:"EPD_SW"},
    fp="Package_TO_SOT_SMD:SOT-23")
add("R11", "2.2", "R", {1:"EPD_RESE", 2:"GND"}, fp=FP_R)   # RESE sense resistor
# diode orientation per datasheet reference circuit (p.24): D3=boost rectifier
# (SW->VGH); D4/D5 form the inverting charge pump for the negative VGL rail.
add("D3", "MBR0530", "D_Schottky", {1:"EPD_SW", 2:"EPD_VGH"}, fp=FP_D_SOD123)     # ds D1: anode SW  -> cathode VGH
add("D4", "MBR0530", "D_Schottky", {1:"EPD_CPMID", 2:"GND"}, fp=FP_D_SOD123)      # ds D2: anode CPMID -> cathode GND
add("D5", "MBR0530", "D_Schottky", {1:"EPD_VGL", 2:"EPD_CPMID"}, fp=FP_D_SOD123)  # ds D3: anode VGL -> cathode CPMID
# 50V, not the datasheet's minimum 25V.  VGH runs near +20 V and VGL near -20 V;
# an 0805 25V X7R at 20 V bias retains only ~20-30 % of its nominal value, so a
# nominal 1 uF would behave like 250 nF exactly where the charge pump needs it.
# 50V parts in the same 0805 body cost the same and land near 60 % retention.
add("C9",  "1uF/50V", "C", {1:"EPD_SW", 2:"EPD_CPMID"}, fp=FP_C)   # flying cap (ref C3)
add("C10", "1uF/50V", "C", {1:"EPD_VGH", 2:"GND"}, fp=FP_C)        # ref C2
add("C11", "1uF/50V", "C", {1:"EPD_VGL", 2:"GND"}, fp=FP_C)        # ref C4
# rail decoupling caps
add("C12", "1uF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)               # VCI/VDDIO (ref C0)
add("C13", "1uF", "C", {1:"EPD_VDD", 2:"GND"}, fp=FP_C)            # VDD core  (ref C1)
add("C14", "1uF/50V", "C", {1:"EPD_VSH1", 2:"GND"}, fp=FP_C)      # ref C5
add("C15", "1uF/50V", "C", {1:"EPD_VSH2", 2:"GND"}, fp=FP_C)      # ref C6
add("C16", "1uF/50V", "C", {1:"EPD_VSL", 2:"GND"}, fp=FP_C)       # ref C7
add("C17", "1uF/50V", "C", {1:"EPD_VCOM", 2:"GND"}, fp=FP_C)      # ref C8
# VPP link.  The panel datasheet's reference circuit (p.24) leaves VPP
# unconnected -- only VCI/VDDIO, VDD, VSH1, VSL and VCOM carry caps there.
# Tying VPP to VCI is what most SSD1681-class modules do and is harmless (OTP
# programming needs a far higher voltage than 3.3 V), but routing it through a
# link means it can be lifted to match the reference exactly if the panel
# misbehaves.  Populated by default.
add("R23", "0", "R", {1:"EPD_VPP", 2:"+3V3"}, fp=FP_R)
# optional external I2C temp sensor pull-ups (DNP by default)
add("R12", "10k (DNP)", "R", {1:"EPD_TSCL", 2:"+3V3"}, fp=FP_R, dnp=True)
add("R13", "10k (DNP)", "R", {1:"EPD_TSDA", 2:"+3V3"}, fp=FP_R, dnp=True)
add("J4", "I2C temp (optional)", "Conn_1x04",
    {1:"+3V3", 2:"GND", 3:"EPD_TSCL", 4:"EPD_TSDA"},
    fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")

# --- UART console + expansion headers ---
add("J5", "UART", "Conn_1x04",
    {1:"+3V3", 2:"GND", 3:"UART_TXD0", 4:"UART_RXD0"},
    fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
# J6 -- expansion header, 2x4 (0.1").
#
# This was a 2x10 breaking out fifteen spare GPIOs on the ESP32-S3.  The C6 does
# not have fifteen spare GPIOs; after the panel, the buttons, USB, UART0 and the
# two strapping pins there are exactly four left, and shrinking the connector is
# the honest way to say so.  A 2x10 with twelve grounds on it would only look
# like it kept the capability.
#
#     1  +3V3            2  GND
#     3  I2C SDA   IO10  4  I2C SCL  IO11
#     5  ADC/IRQ   IO1   6  GND
#     7  GPIO      IO8   8  GND
#
# What survived the move, and why these four pins:
#
#   * Pin 5 (IO1) is the one pin that had to be defended.  It is ADC1_CH1 *and*
#     LP_GPIO1, so it is simultaneously the board's only spare analog input and
#     the only header pin that can wake the chip from deep sleep through EXT1.
#     On the S3 those were two separate jobs on three separate pins (EXP_ADC_A,
#     EXP_ADC_B, EXP_IRQ); here one pin does all of it, which means a sensor
#     that needs an interrupt and a sensor that needs an analog input are now
#     mutually exclusive.  That is a real loss and it is the price of the part.
#     It faces a GND pin so an analog source still gets a short return.
#   * Pins 3/4 (IO10/IO11) are the two remaining general-purpose digital pins
#     with no strapping or LP-domain baggage at all, which makes them the right
#     pair to label I2C.  As on the S3 the label is a convention -- the C6
#     routes I2C through the GPIO matrix -- and R26/R27 are the bus pull-ups,
#     DNP because most sensor breakouts carry their own.
#   * Pin 7 (IO8) is a strapping pin and is the weakest position on the header:
#     it must be HIGH at reset for joint download boot (datasheet Table 4-3;
#     GPIO8 = 0 with GPIO9 = 0 is an invalid combination).  R28 holds it there.
#     Anything plugged in here must not drive it low through reset, or the board
#     stops being flashable over USB.  It is otherwise an ordinary GPIO.
#
# What is gone, so it is not looked for: the four-wire SPI block.  SPI2's IO MUX
# pins on the C6 are GPIO2/4/5/6/7 + GPIO16, all of which are buttons or UART0
# here, and there are not four spare matrix-routable pins left to build a
# software SPI block out of either.  A SPI peripheral has to share pins 3/4/5/7.
add("J6", "GPIO expansion", "Conn_2x04", {
    1:"+3V3",        2:"GND",
    3:"EXP_SDA",     4:"EXP_SCL",
    5:"EXP_ADC_IRQ", 6:"GND",
    7:"EXP_IO8",     8:"GND",
}, fp="Connector_PinHeader_2.54mm:PinHeader_2x04_P2.54mm_Vertical")
# GPIO8 boot-mode strap pull-up.  Required, not optional, and not DNP: GPIO8 is
# floating by default (datasheet Table 4-1) and must read 1 at reset for joint
# download boot to be entered reliably.  10k, not 100k, because this one has to
# win against whatever a user hangs off J6 pin 7, not just against pin leakage.
add("R28", "10k", "R", {1:"+3V3", 2:"EXP_IO8"}, fp=FP_R)
# I2C bus pull-ups for J6 pins 3/4.  DNP by default: nearly every I2C breakout
# already fits its own pair, and two sets in parallel halve the bus impedance.
# Fit these (4.7k) only when the sensor board has none, or when a long ribbon
# needs stiffer edges.  They idle at zero current while the bus sits high, so
# they cost nothing in deep sleep either way.
add("R26", "4.7k (DNP)", "R", {1:"+3V3", 2:"EXP_SDA"}, fp=FP_R, dnp=True)
add("R27", "4.7k (DNP)", "R", {1:"+3V3", 2:"EXP_SCL"}, fp=FP_R, dnp=True)

# --- power flags (ERC: mark externally-sourced nets as driven) ---
# ERC looks for a power_out pin on every net that feeds a power_in pin.  These
# nets are all sourced from outside the schematic -- through a passive connector
# pin, which ERC cannot recognise as a driver -- so each needs a flag or ERC
# reports a spurious power_pin_not_driven error.
add("#FLG1", "PWR_FLAG", "PWR_FLAG", {1:"VBUS"}, in_bom=False)
add("#FLG2", "PWR_FLAG", "PWR_FLAG", {1:"GND"},  in_bom=False)
# Battery side: the cell arrives on J3, a passive 2-pin connector.  PROT_VDD is
# the cell positive after R24 (U4's supply, decoupled by C21) and BATT_NEG is the
# cell negative between J3 pin 2 and Q2's S1 -- both feed DW01A power_in pins.
add("#FLG3", "PWR_FLAG", "PWR_FLAG", {1:"PROT_VDD"}, in_bom=False)
add("#FLG4", "PWR_FLAG", "PWR_FLAG", {1:"BATT_NEG"}, in_bom=False)


# ----------------------------------------------------------------------------
# Self-checks.  These run on every generate and fail loudly, because the netlist
# is a pile of string literals: a typo or a half-finished rename silently
# produces a schematic that still passes ERC while a signal goes nowhere.
# ----------------------------------------------------------------------------
# every real (BOM) component must carry a footprint or "Update PCB from
# Schematic" fails; power-flag pseudo-components legitimately have none.
missing = [i["ref"] for i in instances if i["in_bom"] and not i["fp"]]
if missing:
    raise SystemExit(f"components without a footprint: {', '.join(missing)}")

_errors = []

# duplicate reference designators
_seen = {}
for i in instances:
    if i["ref"] in _seen:
        _errors.append(f"duplicate reference designator {i['ref']}")
    _seen[i["ref"]] = i

# every net key must name a pin that actually exists on that symbol
_nets = {}
for i in instances:
    _pins = {n: e for n, nm, e in symdefs[i["lib"]].pins}
    for num, net in i["nets"].items():
        if num not in _pins:
            _errors.append(f"{i['ref']}: pin {num!r} does not exist on {i['lib']}")
            continue
        if net is not None:
            _nets.setdefault(net, []).append((i["ref"], num, _pins[num], i["dnp"]))

for net, members in sorted(_nets.items()):
    # a net touching one pin is a dangling signal -- usually a rename that was
    # applied to one end of a connection but not the other.
    if len(members) < 2:
        _errors.append(f"net {net!r} has a single member: {members}")
    # ...and the same thing once the DNP parts are depopulated
    elif len([x for x in members if not x[3]]) < 2:
        _errors.append(f"net {net!r} goes open when DNP parts are unpopulated: {members}")
    # two things trying to drive the same wire
    drivers = [x for x in members
               if x[2] in ("output", "power_out", "open_collector")]
    if len(drivers) > 1:
        _errors.append(f"net {net!r} has {len(drivers)} drivers: {drivers}")

if _errors:
    raise SystemExit("netlist self-check failed:\n  " + "\n  ".join(_errors))
print(f"self-check OK: {len(instances)} components, {len(_nets)} nets")

# ----------------------------------------------------------------------------
# Emit the KiCad files.
#
# Everything above is import-safe: definitions and self-checks only.  The file
# writing lives behind the __main__ guard so that tooling can `import gen_sch`
# to inspect the netlist (BOM cross-checks, connectivity audits) without the
# side effect of rewriting the schematic with fresh UUIDs -- which shows up as
# a spurious diff in every generated file.
# ----------------------------------------------------------------------------
def main():
    COLS = 6
    COL_W = 63.5    # 25 * 2.54
    ROW_H = 76.2    # 30 * 2.54
    X0, Y0 = 50.8, 50.8   # both multiples of 1.27 (keeps every endpoint on grid)

    # size the sheet to the content so nothing is clipped off-page.  Use a "User"
    # paper size computed from the grid extent plus room for global-label text.
    ROWS_TOTAL = (len(instances) + COLS - 1) // COLS
    MAX_W = max(sd.width for sd in symdefs.values())
    MAX_H = max(sd.height for sd in symdefs.values())
    LABEL_ROOM = 45.0     # global-label text length allowance
    PAGE_W = X0 + (COLS - 1) * COL_W + MAX_W / 2 + PIN_LEN + GRID + LABEL_ROOM + X0
    NOTE_Y = Y0 + ROWS_TOTAL * ROW_H
    NOTE_ROOM = 16 * GRID * 1.5      # room for the stacked sheet notes below the grid
    PAGE_H = NOTE_Y + max(MAX_H / 2, GRID) + NOTE_ROOM + Y0

    out = []
    out.append('(kicad_sch (version 20231120) (generator "epaper_gen")')
    out.append(f'  (uuid "{ROOT_UUID}")')
    out.append(f'  (paper "User" {PAGE_W:.2f} {PAGE_H:.2f})')
    out.append('  (lib_symbols')
    for name in symdefs:
        out.append(symdefs[name].lib_sexpr())
    out.append('  )')

    wire_lines = []
    label_lines = []
    text_lines = []
    nc_lines = []
    sym_lines = []

    LABEL_SHAPE = {
        "input": "input", "power_in": "input",
        "output": "output", "power_out": "output", "open_collector": "output",
        "bidirectional": "bidirectional",
    }

    def place_label(x, y, net, ang, key, shape="passive", justify=None):
        # text extends away from the symbol: right-side labels (ang 0) are left
        # justified, left-side labels (ang 180) are right justified
        if justify is None:
            justify = "right" if int(ang) == 180 else "left"
        label_lines.append(
            f'  (global_label "{net}" (shape {shape}) (at {x:.3f} {y:.3f} {ang}) (fields_autoplaced)\n'
            f'    (effects (font (size 1.27 1.27)) (justify {justify}))\n'
            f'    (uuid "{U("label:" + key)}"))'
        )

    def place_text(x, y, text, key):
        text_lines.append(
            f'  (text "{text}" (exclude_from_sim no) (at {x:.3f} {y:.3f} 0)\n'
            f'    (effects (font (size 1.27 1.27)) (justify left))\n'
            f'    (uuid "{U("text:" + key)}"))'
        )

    for idx, inst in enumerate(instances):
        sd = symdefs[inst["lib"]]
        col = idx % COLS
        row = idx // COLS
        px = X0 + col * COL_W
        py = Y0 + row * ROW_H
        ref = inst["ref"]
        uu = U(f"sym:{ref}")
        bom = 'yes' if inst["in_bom"] else 'no'
        sym_lines.append(f'  (symbol (lib_id "epaper:{inst["lib"]}") (at {px:.3f} {py:.3f} 0) (unit 1)')
        sym_lines.append(f'    (in_bom {bom}) (on_board yes)' + (' (dnp yes)' if inst["dnp"] else ''))
        sym_lines.append(f'    (uuid "{uu}")')
        sym_lines.append(f'    (property "Reference" "{ref}" (at {px:.3f} {py - sd.height/2 - 3.81:.3f} 0)')
        sym_lines.append(f'      (effects (font (size 1.27 1.27))))')
        val = inst["value"].replace('"', "")
        sym_lines.append(f'    (property "Value" "{val}" (at {px:.3f} {py + sd.height/2 + 3.81:.3f} 0)')
        sym_lines.append(f'      (effects (font (size 1.27 1.27))))')
        fp = inst["fp"].replace('"', "")
        sym_lines.append(f'    (property "Footprint" "{fp}" (at {px:.3f} {py:.3f} 0)')
        sym_lines.append(f'      (effects (font (size 1.27 1.27)) hide))')
        # pin instance uuids
        for num, name, et in sd.pins:
            sym_lines.append(f'    (pin "{num}" (uuid "{U(f"pin:{ref}:{num}")}"))')
        sym_lines.append('    (instances')
        sym_lines.append(f'      (project "epaper-display"')
        sym_lines.append(f'        (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))')
        sym_lines.append('  )')

        # wires + labels per pin
        for num, name, et in sd.pins:
            lx, ly, ang, side = sd.pin_geom[num]
            # schematic connection point (library +Y up -> schematic +Y down)
            cx = px + lx
            cy = py - ly
            net = inst["nets"].get(num, NC)
            if net is None and et == 'no_connect':
                # pin is already electrically a no-connect; adding a NC flag is an
                # ERC error, and the bare pin raises no violation, so leave it.
                continue
            if side == 'L':
                ex = cx - GRID
                lab_ang = 180
                lab_justify = 'right'
            else:
                ex = cx + GRID
                lab_ang = 0
                lab_justify = 'left'
            ey = cy
            if net is None:
                # no-connect flag at the pin tip
                nc_lines.append(f'  (no_connect (at {cx:.3f} {cy:.3f}) (uuid "{U(f"nc:{ref}:{num}")}"))')
                continue
            wire_lines.append(
                f'  (wire (pts (xy {cx:.3f} {cy:.3f}) (xy {ex:.3f} {ey:.3f}))\n'
                f'    (stroke (width 0) (type default)) (uuid "{U(f"wire:{ref}:{num}")}"))'
            )
            place_label(ex, ey, net, lab_ang, f"{ref}:{num}",
                        LABEL_SHAPE.get(et, "passive"), lab_justify)

    for _n, _note in enumerate([
        "J6 (2x4 expansion) is 1=3V3 2=GND, 3/4=I2C SDA/SCL (IO10/IO11, R26/R27",
        "   pull-ups DNP), 5=ADC/IRQ (IO1 = ADC1_CH1 AND LP_GPIO1 - the only spare",
        "   pin that is both analog and EXT1-wake capable), 6/8=GND, 7=IO8 spare.",
        "   There is no SPI block: SPI2's IO MUX pins on the C6 (IO2/4/5/6/7/16)",
        "   are all buttons or UART0 here. Four spare GPIOs is all the part has.",
        "J6 pin 7 is IO8, a STRAPPING pin held high by R28. Do not let anything",
        "   plugged into J6 drive it low through reset (IO8=0 with IO9=0 is an",
        "   invalid boot mode) or the board stops being flashable over USB.",
        "R15 pulls IO15 HIGH (the S3 revision pulled its strap low). IO15 selects",
        "   the JTAG source once EFUSE_JTAG_SEL_ENABLE is burnt: high = USB",
        "   Serial/JTAG, low = the MTMS/MTDI/MTCK/MTDO pads - which are IO4-IO7,",
        "   i.e. four of the buttons. Required, not optional: IO15 has no internal",
        "   pull and must not float (module datasheet 4.4).",
        "J3 is the RAW CELL, not a protected pack: pin 1 = B+, pin 2 = B- on its own net.",
        "   1S protection (U4 DW01A + Q2 FS8205A) is on-board, in the low side between B-",
        "   and GND, per the DW01A datasheet application circuit p.9.",
        "There is NO reverse-polarity protection. The old D6 crowbar was removed: it would",
        "   now sit downstream of a reversed connector with nothing left to clear the fault,",
        "   and an 80C 300mAh cell sources ~24A into a 1A diode. CHECK PH2.0 POLARITY WITH",
        "   A METER before first plug-in - a reversed cell will destroy U4.",
        "Keep U2 as the -2 (4.20V) option: U4 trips overcharge at 4.30V, so the 4.35V -3",
        "   part would fight the protection. Do NOT fit it even though the cell is LiHV.",
        "Q2 pinout is 1=S1 2=D 3=S2 4=G2 5=D 6=G1, per the Package and Pin Configuration",
        "   drawing in components/fs8205a-techpublic.pdf. Each FET half sits at one END of",
        "   the package and the common drain is on the two MIDDLE pins. This is NOT the",
        "   commonly-quoted 8205A mapping (2=G1, 6=D1) - do not copy that from other",
        "   designs. Confirm once with a DMM: shorted pair = drains, ~0.6V in diode mode",
        "   to the drain node = a source, remaining two = gates.",
        "U3 (SOT-23-5, 1=IN 2=GND 3=EN 4=NC 5=OUT) accepts TLV75733PDBVR / AP2112K-3.3 /",
        "   XC6220B331MR unchanged. EN is tied to IN - do not leave it floating.",
        "U3 is the DBV package: RthJA 231 C/W, no thermal pad. Fine for this board's",
        "   burst load (C6 Wi-Fi TX peaks at 382mA, module datasheet Table 6-4), but do",
        "   NOT draw a sustained 500mA from +3V3 via J6.",
        "Buttons SW3-SW8 use external 100k pull-ups (R17-R22) so they hold a defined level",
        "   through deep sleep; firmware may still enable LP pull-ups harmlessly in parallel.",
        "All six buttons sit on IO2-IO7 because the C6's LP (RTC) IOs are IO0-IO7 and",
        "   nothing else - only those eight pins can wake the chip through EXT1. IO0 is",
        "   VBAT_SENSE (ADC1_CH0), IO1 goes to J6, and that is the whole LP budget.",
        "SW3/SW4 sit on MTMS/MTDI, which are also SDIO-slave clock-edge straps. R17/R18",
        "   latch them high at reset; this board never uses SDIO slave, so it is inert.",
        "U1 footprint is Espressif:ESP32-C6-WROOM-1, from Espressif's official KiCad",
        "   library (install via KiCad's Plugin and Content Manager). Stock KiCad's",
        "   RF_Module library has no C6-WROOM-1 - it only carries ESP32-C6-MINI-1.",
    ]):
        place_text(X0, NOTE_Y + _n * GRID * 1.5, _note, f"note{_n}")

    out.extend(sym_lines)
    out.extend(wire_lines)
    out.extend(nc_lines)
    out.extend(label_lines)
    out.extend(text_lines)

    # sheet instances block
    out.append('  (sheet_instances')
    out.append('    (path "/" (page "1"))')
    out.append('  )')
    out.append(')')

    with open(SCH, "w") as f:
        f.write("\n".join(out) + "\n")
    print("wrote", SCH, "with", len(instances), "components")

    # ----------------------------------------------------------------------------
    # Emit a standalone symbol library + project sym-lib-table so the 'epaper'
    # library nickname resolves (silences lib_symbol_issues warnings and lets the
    # symbols be edited in the KiCad symbol editor).
    # ----------------------------------------------------------------------------
    lib = ['(kicad_symbol_lib (version 20231120) (generator "epaper_gen")']
    for name in symdefs:
        lib.append(symdefs[name].lib_sexpr(prefix="", indent="  "))
    lib.append(')')
    with open("epaper.kicad_sym", "w") as f:
        f.write("\n".join(lib) + "\n")
    print("wrote epaper.kicad_sym")

    with open("sym-lib-table", "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n'
                '  (lib (name "epaper")(type "KiCad")(uri "${KIPRJMOD}/epaper.kicad_sym")'
                '(options "")(descr "E-paper display project symbols"))\n)\n')
    print("wrote sym-lib-table")

    # keep the project file's root-sheet UUID in sync with the schematic
    PRO = "epaper-display.kicad_pro"
    if os.path.exists(PRO):
        import re as _re
        txt = open(PRO).read()
        txt = _re.sub(r'"[0-9a-fA-F-]{36}",\n      "Root"', f'"{ROOT_UUID}",\n      "Root"', txt)
        txt = txt.replace("SHEET_UUID_PLACEHOLDER", ROOT_UUID)
        open(PRO, "w").write(txt)
        print("synced", PRO, "root uuid ->", ROOT_UUID)



if __name__ == "__main__":
    main()
