#!/usr/bin/env python3
"""Generator for the ESP32-S3-WROOM-1 e-paper display KiCad 8 schematic.

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

def U():
    return str(uuid.uuid4())

ROOT_UUID = U()

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

# ESP32-S3-WROOM-1 module (41 pins)
MODULE_PINS = [
    (1,"GND","power_in"),(2,"3V3","power_in"),(3,"EN","input"),
    (4,"IO4","bidirectional"),(5,"IO5","bidirectional"),(6,"IO6","bidirectional"),
    (7,"IO7","bidirectional"),(8,"IO15","bidirectional"),(9,"IO16","bidirectional"),
    (10,"IO17","bidirectional"),(11,"IO18","bidirectional"),(12,"IO8","bidirectional"),
    (13,"IO19","bidirectional"),(14,"IO20","bidirectional"),(15,"IO3","bidirectional"),
    (16,"IO46","bidirectional"),(17,"IO9","bidirectional"),(18,"IO10","bidirectional"),
    (19,"IO11","bidirectional"),(20,"IO12","bidirectional"),(21,"IO13","bidirectional"),
    (22,"IO14","bidirectional"),(23,"IO21","bidirectional"),(24,"IO47","bidirectional"),
    (25,"IO48","bidirectional"),(26,"IO45","bidirectional"),(27,"IO0","bidirectional"),
    (28,"IO35","bidirectional"),(29,"IO36","bidirectional"),(30,"IO37","bidirectional"),
    (31,"IO38","bidirectional"),(32,"IO39","bidirectional"),(33,"IO40","bidirectional"),
    (34,"IO41","bidirectional"),(35,"IO42","bidirectional"),(36,"RXD0","bidirectional"),
    (37,"TXD0","bidirectional"),(38,"IO2","bidirectional"),(39,"IO1","bidirectional"),
    (40,"GND","power_in"),(41,"EPAD","power_in"),
]
mk("ESP32-S3-WROOM-1", MODULE_PINS)

# E-paper 24-pin FPC breakout
EPD_PINS = [
    (1,"NC","no_connect"),(2,"GDR","output"),(3,"RESE","input"),(4,"NC","no_connect"),
    (5,"VSH2","passive"),(6,"TSCL","output"),(7,"TSDA","bidirectional"),(8,"BS1","input"),
    (9,"BUSY","output"),(10,"RES#","input"),(11,"D/C#","input"),(12,"CS#","input"),
    (13,"SCL","input"),(14,"SDA","input"),(15,"VDDIO","power_in"),(16,"VCI","power_in"),
    (17,"VSS","power_in"),(18,"VDD","passive"),(19,"VPP","power_in"),(20,"VSH1","passive"),
    (21,"VGH","passive"),(22,"VSL","passive"),(23,"VGL","passive"),(24,"VCOM","passive"),
]
mk("EPD_AES200200A00", EPD_PINS)

# USB-C receptacle, USB 2.0 16-pin.  Pin *numbers* are the real A/B pad names so
# they map 1:1 onto Connector_USB:USB_C_Receptacle_GCT_USB4085 (pads A1 A4 A5 A6
# A7 A8 A9 A12 / B1 B4 B5 B6 B7 B8 B9 B12 + four shield pads all numbered S1).
# The duplicated rows MUST be paralleled in the netlist below or the cable only
# works in one orientation.
mk("USB_C_Receptacle_USB2.0", [
    ("A1","GND","power_in"),("A4","VBUS","power_in"),("A5","CC1","passive"),
    ("A6","D+","bidirectional"),("A7","D-","bidirectional"),("A8","SBU1","passive"),
    ("A9","VBUS","power_in"),("A12","GND","power_in"),
    ("B1","GND","power_in"),("B4","VBUS","power_in"),("B5","CC2","passive"),
    ("B6","D+","bidirectional"),("B7","D-","bidirectional"),("B8","SBU2","passive"),
    ("B9","VBUS","power_in"),("B12","GND","power_in"),
    ("S1","SHIELD","passive"),
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
mk("Conn_2x12", [ (i+1, str(i+1), "passive") for i in range(24) ])

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

# --- ESP32-S3-WROOM-1 ---
add("U1", "ESP32-S3-WROOM-1-N8", "ESP32-S3-WROOM-1", {
    1:"GND", 2:"+3V3", 3:"EN",
    4:"EPD_SCLK", 5:"EPD_MOSI", 6:"EPD_CS", 7:"EPD_DC",
    8:"EXP_IO15", 9:"EXP_IO16", 10:"EXP_IO17", 11:"EXP_IO18",
    12:"EPD_RST", 13:"USB_DM_MCU", 14:"USB_DP_MCU",
    15:"STRAP_IO3", 16:NC, 17:"EPD_BUSY",
    18:"BTN_DOWN", 19:"BTN_LEFT", 20:"BTN_RIGHT", 21:"BTN_SELECT", 22:"BTN_CANCEL",
    23:"EXP_IO21", 24:"EXP_IO47", 25:"EXP_IO48", 26:NC, 27:"BOOT",
    28:"EXP_IO35", 29:"EXP_IO36", 30:"EXP_IO37", 31:"EXP_IO38", 32:"EXP_IO39",
    33:"EXP_IO40", 34:"EXP_IO41", 35:"EXP_IO42", 36:"UART_RXD0", 37:"UART_TXD0",
    38:"BTN_UP", 39:"VBAT_SENSE", 40:"GND", 41:"GND",
}, fp="RF_Module:ESP32-S3-WROOM-1")

# --- E-paper FPC breakout ---
add("J1", "AES200200A00 FPC", "EPD_AES200200A00", {
    1:NC, 2:"EPD_GDR", 3:"EPD_RESE", 4:NC, 5:"EPD_VSH2",
    6:"EPD_TSCL", 7:"EPD_TSDA", 8:"GND", 9:"EPD_BUSY", 10:"EPD_RST",
    11:"EPD_DC", 12:"EPD_CS", 13:"EPD_SCLK", 14:"EPD_MOSI",
    15:"+3V3", 16:"+3V3", 17:"GND", 18:"EPD_VDD", 19:"EPD_VPP",
    20:"EPD_VSH1", 21:"EPD_VGH", 22:"EPD_VSL", 23:"EPD_VGL", 24:"EPD_VCOM",
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
    "S1":"GND",
}, fp="Connector_USB:USB_C_Receptacle_GCT_USB4085")
add("R1", "5.1k", "R", {1:"CC1", 2:"GND"}, fp=FP_R)
add("R2", "5.1k", "R", {1:"CC2", 2:"GND"}, fp=FP_R)
# 0 ohm, not 22 ohm: the ESP32-S3 USB PHY already contains its series
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
# Active-low to GND.  All six are RTC GPIOs (GPIO0-21), so any of them can serve
# as a deep-sleep wake source -- which is exactly why they get *external*
# pull-ups: the digital-domain internal pull-ups drop out in deep sleep, and an
# EXT1 wake source that floats produces phantom wakes that quietly eat the
# battery.  100k (not 10k) keeps the held-button current to 33 uA.
BUTTONS = [("SW3","BTN_UP"), ("SW4","BTN_DOWN"), ("SW5","BTN_LEFT"),
           ("SW6","BTN_RIGHT"), ("SW7","BTN_SELECT"), ("SW8","BTN_CANCEL")]
for _i, (_sw, _net) in enumerate(BUTTONS):
    add(_sw, _net, "SW_PUSH", {1:_net, 2:"GND"}, fp=FP_SW_6MM)
    add(f"R{17+_i}", "100k", "R", {1:"+3V3", 2:_net}, fp=FP_R)
# 100k rather than 10k: these only ever fight a CMOS input's leakage, and 10k
# would burn 330 uA whenever firmware drives the pin against the resistor.
add("R14", "100k", "R", {1:"+3V3", 2:"EPD_CS"}, fp=FP_R)
# Populated, NOT DNP.  Module datasheet 4.4: GPIO3 "does not have any internal
# pull resistors and the strapping value must be controlled by the external
# circuit that cannot be in a high impedance state."
add("R15", "10k", "R", {1:"STRAP_IO3", 2:"GND"}, fp=FP_R)
add("R16", "100k", "R", {1:"EPD_RST", 2:"GND"}, fp=FP_R)

# --- Battery sense divider (into ADC1_CH0 / GPIO1) ---
# 1M/1M, not 100k/100k: the divider is across the cell permanently, and at 100k
# it drew 21 uA -- roughly triple the ESP32-S3's own 7-8 uA deep-sleep current
# on a device whose entire premise is deep sleep.  1M brings that to 2.1 uA.
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
# GPIO2/10/11/12/13/14 are dedicated to SW3-SW8 (nets BTN_*) and are
# deliberately not broken out here; the freed pins become extra ground returns.
add("J6", "GPIO expansion", "Conn_2x12", {
    1:"+3V3", 2:"GND",
    3:"EXP_IO15", 4:"EXP_IO16", 5:"EXP_IO17", 6:"EXP_IO18",
    7:"EXP_IO21", 8:"EXP_IO35", 9:"EXP_IO36", 10:"EXP_IO37", 11:"EXP_IO38",
    12:"EXP_IO39", 13:"EXP_IO40", 14:"EXP_IO41", 15:"EXP_IO42", 16:"EXP_IO47",
    17:"EXP_IO48", 18:"GND",
    19:"GND", 20:"GND", 21:"GND", 22:"GND", 23:"GND", 24:"GND",
}, fp="Connector_PinHeader_2.54mm:PinHeader_2x12_P2.54mm_Vertical")

# --- power flags (ERC: mark externally-sourced nets as driven) ---
add("#FLG1", "PWR_FLAG", "PWR_FLAG", {1:"VBUS"}, in_bom=False)
add("#FLG2", "PWR_FLAG", "PWR_FLAG", {1:"GND"},  in_bom=False)


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

    def place_label(x, y, net, ang, shape="passive", justify=None):
        # text extends away from the symbol: right-side labels (ang 0) are left
        # justified, left-side labels (ang 180) are right justified
        if justify is None:
            justify = "right" if int(ang) == 180 else "left"
        label_lines.append(
            f'  (global_label "{net}" (shape {shape}) (at {x:.3f} {y:.3f} {ang}) (fields_autoplaced)\n'
            f'    (effects (font (size 1.27 1.27)) (justify {justify}))\n'
            f'    (uuid "{U()}"))'
        )

    def place_text(x, y, text):
        text_lines.append(
            f'  (text "{text}" (exclude_from_sim no) (at {x:.3f} {y:.3f} 0)\n'
            f'    (effects (font (size 1.27 1.27)) (justify left))\n'
            f'    (uuid "{U()}"))'
        )

    for idx, inst in enumerate(instances):
        sd = symdefs[inst["lib"]]
        col = idx % COLS
        row = idx // COLS
        px = X0 + col * COL_W
        py = Y0 + row * ROW_H
        ref = inst["ref"]
        uu = U()
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
            sym_lines.append(f'    (pin "{num}" (uuid "{U()}"))')
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
                nc_lines.append(f'  (no_connect (at {cx:.3f} {cy:.3f}) (uuid "{U()}"))')
                continue
            wire_lines.append(
                f'  (wire (pts (xy {cx:.3f} {cy:.3f}) (xy {ex:.3f} {ey:.3f}))\n'
                f'    (stroke (width 0) (type default)) (uuid "{U()}"))'
            )
            place_label(ex, ey, net, lab_ang, LABEL_SHAPE.get(et, "passive"), lab_justify)

    for _n, _note in enumerate([
        "J6 IO35-37 and IO47/48 assume non-octal-PSRAM, non-R16V module",
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
        "   burst load, but do NOT draw a sustained 500mA from +3V3 via J6.",
        "Buttons SW3-SW8 use external 100k pull-ups (R17-R22) so they hold a defined level",
        "   through deep sleep; firmware may still enable RTC pull-ups harmlessly in parallel.",
    ]):
        place_text(X0, NOTE_Y + _n * GRID * 1.5, _note)

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
