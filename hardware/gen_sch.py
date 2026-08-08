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

# USB-C receptacle (logical pins)
mk("USB_C_Receptacle", [
    (1,"VBUS","power_in"),(2,"GND","power_in"),(3,"CC1","passive"),(4,"CC2","passive"),
    (5,"D+","bidirectional"),(6,"D-","bidirectional"),(7,"SBU1","passive"),
    (8,"SBU2","passive"),(9,"SHIELD","passive"),
])

# MCP73831 SOT-23-5
mk("MCP73831", [
    (1,"STAT","open_collector"),(2,"VSS","power_in"),(3,"VBAT","power_out"),
    (4,"VDD","power_in"),(5,"PROG","passive"),
])

# MCP1825S-3302 SOT-223-3
mk("MCP1825S-3302", [
    (1,"VIN","power_in"),(2,"GND","power_in"),(3,"VOUT","power_out"),
])

# N-channel MOSFET SOT-23 (G,S,D)
mk("MOSFET_N", [ (1,"G","input"),(2,"S","passive"),(3,"D","passive") ])

# generic 2-pin passives
mk("R", [ (1,"1","passive"),(2,"2","passive") ])
mk("C", [ (1,"1","passive"),(2,"2","passive") ])
mk("L", [ (1,"1","passive"),(2,"2","passive") ])
mk("D_Schottky", [ (1,"A","passive"),(2,"K","passive") ])
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
FP_D_SOD123 = "Diode_SMD:D_SOD-123"
FP_L_1210 = "Inductor_SMD:L_1210_3225Metric"
# every tactile push button is the same FSJM-series 6x6mm 4-pin through-hole
# part (Omron/Alps 6.5mm x 4.5mm pad pitch), which this footprint models.
FP_SW_6MM = "Button_Switch_THT:SW_PUSH_6mm"

instances = []
def add(ref, value, lib, nets, fp="", dnp=False, in_bom=True):
    instances.append(dict(ref=ref, value=value, lib=lib, nets=nets, fp=fp, dnp=dnp, in_bom=in_bom))

# --- ESP32-S3-WROOM-1 ---
add("U1", "ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1", {
    1:"GND", 2:"+3V3", 3:"EN",
    4:"EPD_SCLK", 5:"EPD_MOSI", 6:"EPD_CS", 7:"EPD_DC",
    8:"EXP_IO15", 9:"EXP_IO16", 10:"EXP_IO17", 11:"EXP_IO18",
    12:"EPD_RST", 13:"USB_DM_MCU", 14:"USB_DP_MCU",
    15:NC, 16:NC, 17:"EPD_BUSY",
    18:"EXP_IO10", 19:"EXP_IO11", 20:"EXP_IO12", 21:"EXP_IO13", 22:"EXP_IO14",
    23:"EXP_IO21", 24:"EXP_IO47", 25:"EXP_IO48", 26:NC, 27:"BOOT",
    28:"EXP_IO35", 29:"EXP_IO36", 30:"EXP_IO37", 31:"EXP_IO38", 32:"EXP_IO39",
    33:"EXP_IO40", 34:"EXP_IO41", 35:"EXP_IO42", 36:"UART_RXD0", 37:"UART_TXD0",
    38:"EXP_IO2", 39:"VBAT_SENSE", 40:"GND", 41:"GND",
}, fp="RF_Module:ESP32-S3-WROOM-1")

# --- E-paper FPC breakout ---
add("J1", "AES200200A00 FPC", "EPD_AES200200A00", {
    1:NC, 2:"EPD_GDR", 3:"EPD_RESE", 4:NC, 5:"EPD_VSH2",
    6:"EPD_TSCL", 7:"EPD_TSDA", 8:"GND", 9:"EPD_BUSY", 10:"EPD_RST",
    11:"EPD_DC", 12:"EPD_CS", 13:"EPD_SCLK", 14:"EPD_MOSI",
    15:"+3V3", 16:"+3V3", 17:"GND", 18:"EPD_VDD", 19:"+3V3",
    20:"EPD_VSH1", 21:"EPD_VGH", 22:"EPD_VSL", 23:"EPD_VGL", 24:"EPD_VCOM",
}, fp="Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal")

# --- USB-C receptacle ---
# TODO(layout): this is a simplified logical 9-pin symbol, while the GCT
# USB4085 receptacle has A/B-numbered pads (A1..A12 / B1..B12 plus shield
# tabs).  The symbol pins therefore do NOT map 1:1 to the physical pads --
# verify/repair the pad assignment (and pair CC1/CC2, D+/D-, VBUS, GND across
# both rows) when laying out the PCB, or swap in the stock KiCad USB-C symbol.
add("J2", "USB-C", "USB_C_Receptacle", {
    1:"VBUS", 2:"GND", 3:"CC1", 4:"CC2", 5:"USB_DP", 6:"USB_DM",
    7:NC, 8:NC, 9:"GND",
}, fp="Connector_USB:USB_C_Receptacle_GCT_USB4085")
add("R1", "5.1k", "R", {1:"CC1", 2:"GND"}, fp=FP_R)
add("R2", "5.1k", "R", {1:"CC2", 2:"GND"}, fp=FP_R)
add("R3", "22", "R", {1:"USB_DP", 2:"USB_DP_MCU"}, fp=FP_R)
add("R4", "22", "R", {1:"USB_DM", 2:"USB_DM_MCU"}, fp=FP_R)
add("D1", "USBLC6-2SC6 (optional)", "USBLC6_ESD",
    {1:"USB_DP", 2:"GND", 3:"USB_DM", 4:"USB_DM", 5:"VBUS", 6:"USB_DP"},
    fp="Package_TO_SOT_SMD:SOT-23-6", dnp=True)

# --- MCP73831 charger ---
add("U2", "MCP73831T-2ACI/OT", "MCP73831", {
    1:"CHG_STAT", 2:"GND", 3:"VBAT", 4:"VBUS", 5:"CHG_PROG",
}, fp="Package_TO_SOT_SMD:SOT-23-5")
add("R5", "4.7k", "R", {1:"CHG_PROG", 2:"GND"}, fp=FP_R)  # I_chg = 1000/4.7k ~= 213 mA
add("R6", "1k", "R", {1:"+3V3", 2:"CHG_LED"}, fp=FP_R)
add("D2", "LED (charge)", "LED", {1:"CHG_LED", 2:"CHG_STAT"},
    fp="LED_THT:LED_D3.0mm")
add("C1", "4.7uF", "C", {1:"VBUS", 2:"GND"}, fp=FP_C)   # charger input
add("C2", "4.7uF", "C", {1:"VBAT", 2:"GND"}, fp=FP_C)   # charger output
add("J3", "LiPo JST-PH", "Conn_JST_PH_2", {1:"VBAT", 2:"GND"},
    fp="Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal")

# --- MCP1825S 3.3V/500mA LDO ---
add("U3", "MCP1825S-3302E/DB", "MCP1825S-3302", {
    1:"VBAT", 2:"GND", 3:"+3V3",
}, fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2")
add("C3", "4.7uF", "C", {1:"VBAT", 2:"GND"}, fp=FP_C)   # LDO input  (>=1uF, X7R)
add("C4", "4.7uF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)   # LDO output (>=1uF, X7R, ESR<1ohm)

# --- MCU support ---
add("C5", "100nF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)
add("C6", "10uF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)
add("R7", "10k", "R", {1:"+3V3", 2:"EN"}, fp=FP_R)
add("C7", "1uF", "C", {1:"EN", 2:"GND"}, fp=FP_C)
add("SW1", "EN/RESET", "SW_PUSH", {1:"EN", 2:"GND"}, fp=FP_SW_6MM)
add("R8", "10k", "R", {1:"+3V3", 2:"BOOT"}, fp=FP_R)
add("SW2", "BOOT", "SW_PUSH", {1:"BOOT", 2:"GND"}, fp=FP_SW_6MM)

# --- User buttons: D-pad + select + cancel ---
# Active-low to GND with no external pull-ups: firmware must configure each pin
# as INPUT_PULLUP.  All six are RTC GPIOs (GPIO0-21), so any of them can serve
# as a deep-sleep wake source.
add("SW3", "BTN_UP",     "SW_PUSH", {1:"EXP_IO2",  2:"GND"}, fp=FP_SW_6MM)
add("SW4", "BTN_DOWN",   "SW_PUSH", {1:"EXP_IO10", 2:"GND"}, fp=FP_SW_6MM)
add("SW5", "BTN_LEFT",   "SW_PUSH", {1:"EXP_IO11", 2:"GND"}, fp=FP_SW_6MM)
add("SW6", "BTN_RIGHT",  "SW_PUSH", {1:"EXP_IO12", 2:"GND"}, fp=FP_SW_6MM)
add("SW7", "BTN_SELECT", "SW_PUSH", {1:"EXP_IO13", 2:"GND"}, fp=FP_SW_6MM)
add("SW8", "BTN_CANCEL", "SW_PUSH", {1:"EXP_IO14", 2:"GND"}, fp=FP_SW_6MM)

# --- Battery sense divider (into ADC1_CH0 / GPIO1) ---
add("R9", "100k", "R", {1:"VBAT", 2:"VBAT_SENSE"}, fp=FP_R)
add("R10", "100k", "R", {1:"VBAT_SENSE", 2:"GND"}, fp=FP_R)
add("C8", "100nF", "C", {1:"VBAT_SENSE", 2:"GND"}, fp=FP_C)

# --- E-paper DC/DC boost + charge pump (reference circuit, datasheet p.24) ---
add("L1", "47uH", "L", {1:"EPD_SW", 2:"+3V3"}, fp=FP_L_1210)   # VCI = +3V3
add("Q1", "Si1304BDL / NX3008NBK", "MOSFET_N",
    {1:"EPD_GDR", 2:"EPD_RESE", 3:"EPD_SW"},
    fp="Package_TO_SOT_SMD:SOT-23")
add("R11", "2.2", "R", {1:"EPD_RESE", 2:"GND"}, fp=FP_R)   # RESE sense resistor
# diode orientation per datasheet reference circuit (p.24): D3=boost rectifier
# (SW->VGH); D4/D5 form the inverting charge pump for the negative VGL rail.
add("D3", "MBR0530", "D_Schottky", {1:"EPD_SW", 2:"EPD_VGH"}, fp=FP_D_SOD123)     # ds D1: anode SW  -> cathode VGH
add("D4", "MBR0530", "D_Schottky", {1:"EPD_CPMID", 2:"GND"}, fp=FP_D_SOD123)      # ds D2: anode CPMID -> cathode GND
add("D5", "MBR0530", "D_Schottky", {1:"EPD_VGL", 2:"EPD_CPMID"}, fp=FP_D_SOD123)  # ds D3: anode VGL -> cathode CPMID
add("C9",  "1uF/25V", "C", {1:"EPD_SW", 2:"EPD_CPMID"}, fp=FP_C)   # flying cap (ref C3)
add("C10", "1uF/25V", "C", {1:"EPD_VGH", 2:"GND"}, fp=FP_C)        # ref C2
add("C11", "1uF/25V", "C", {1:"EPD_VGL", 2:"GND"}, fp=FP_C)        # ref C4
# rail decoupling caps
add("C12", "1uF", "C", {1:"+3V3", 2:"GND"}, fp=FP_C)               # VCI/VDDIO (ref C0)
add("C13", "1uF", "C", {1:"EPD_VDD", 2:"GND"}, fp=FP_C)            # VDD core  (ref C1)
add("C14", "1uF/25V", "C", {1:"EPD_VSH1", 2:"GND"}, fp=FP_C)      # ref C5
add("C15", "1uF/25V", "C", {1:"EPD_VSH2", 2:"GND"}, fp=FP_C)      # ref C6
add("C16", "1uF/25V", "C", {1:"EPD_VSL", 2:"GND"}, fp=FP_C)       # ref C7
add("C17", "1uF/25V", "C", {1:"EPD_VCOM", 2:"GND"}, fp=FP_C)      # ref C8
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
# EXP_IO2/10/11/12/13/14 are now dedicated to SW3-SW8 and are deliberately not
# broken out here; the freed pins become extra ground returns.
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


# every real (BOM) component must carry a footprint or "Update PCB from
# Schematic" fails; power-flag pseudo-components legitimately have none.
missing = [i["ref"] for i in instances if i["in_bom"] and not i["fp"]]
if missing:
    raise SystemExit(f"components without a footprint: {', '.join(missing)}")

# ----------------------------------------------------------------------------
# Emit schematic
# ----------------------------------------------------------------------------
# layout instances on a coarse grid
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
PAGE_H = Y0 + (ROWS_TOTAL - 1) * ROW_H + MAX_H / 2 + Y0

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

out.extend(sym_lines)
out.extend(wire_lines)
out.extend(nc_lines)
out.extend(label_lines)

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
