# E-Paper Display — Hardware (KiCad schematic)

Battery-powered 1.54" e-paper display built around the **ESP32-S3-WROOM-1-N8** module.
This directory contains a **schematic only** — no PCB layout yet, but every
component carries a footprint.

Files:

| File | Purpose |
|------|---------|
| `epaper-display.kicad_pro` | KiCad 8 project |
| `epaper-display.kicad_sch` | Schematic (KiCad 7/8 S-expression, `kicad_sch`) |
| `epaper.kicad_sym` | Project symbol library (referenced by the schematic) |
| `sym-lib-table` | Maps the `epaper` library nickname to `epaper.kicad_sym` |
| `epaper-display-schematic.pdf` | Rendered schematic |
| `gen_sch.py` | Generator that produces the schematic/library from the netlist definition |

The schematic parses and passes ERC cleanly in **KiCad 8.0.9**
(`kicad-cli sch erc` → *0 violations*; `kicad-cli sch export netlist` → correct
netlist). Connectivity is expressed with **global labels**, so the netlist is
correct even though the auto-generated component placement is rough. Re-open in
KiCad and rearrange/route as desired.

> There are intentionally **no long wires drawn between components**: every pin
> has a short stub ending in a global label, and identically-named global labels
> are one net across the whole sheet. So the schematic looks like a field of
> labels rather than a routed drawing, but it is fully connected electrically —
> confirm with *Tools → Edit Symbol Fields* / the netlist export, or hover a
> label to highlight the net.

---

## 1. Architecture overview

```
             USB-C (VBUS 5V)
                  |
                  +--> 22R --> D-/D+ (GPIO19 / GPIO20, native USB-Serial/JTAG)
                  |
                  v
        MCP73831 (SOT-23-5)  Li-ion/LiPo linear charger  (no power-path)
                  |  VBAT
                  v
        single-cell LiPo (JST-PH)  <---- system battery node (VBAT) ---->  MCP1825S
                                                                              |  (SOT-223, 3.3V/500mA LDO)
                                                                              v
                                                                            +3V3 rail
                                                                              |
                        +-----------------------------------------------------+
                        |                                                     |
              ESP32-S3-WROOM-1-N8 (3V3)                        AES200200A00 e-paper (VCI/VDDIO)
              + 100nF + 10uF decoupling                       + on-FPC DC/DC boost & charge pump
```

- **Power in:** one USB-C receptacle provides both **VBUS (charging)** and the
  **native USB** programming/serial link.
- **Charging:** `MCP73831` charges the LiPo. Its `VBAT` pin is the system
  battery node and directly feeds the regulator (see §4 — no power-path).
- **Regulation:** `MCP1825S-3302` (fixed 3.3V, 500 mA, SOT-223) generates the
  `+3V3` rail that powers the module and the display.
- **Programming/serial:** ESP32-S3 native USB-Serial/JTAG on **GPIO19 (D-)** and
  **GPIO20 (D+)**. No external USB-UART bridge required. UART0 (GPIO43/44) is
  also broken out on a header for an optional console.

---

## 2. Regulator choice — MCP1825S (and the dropout trade-off)

The previous revision used an `MCP1700-3302E/TO` (250 mA). The ESP32-S3's Wi-Fi
TX current peaks at roughly **350–500 mA**, which exceeds the MCP1700's ~250 mA
rating and can cause brownouts during transmit. This revision therefore uses the
**MCP1825S-3302** (fixed 3.3V, **500 mA**, SOT-223) to give headroom for those
peaks.

**Dropout trade-off:** the MCP1825/MCP1825S dropout is **210 mV typ / 350 mV max
at 500 mA** (datasheet DS22056B, Table 1-1 & §1.0). To stay in regulation at a
500 mA peak, the input (VBAT) must remain above roughly:

```
VBAT_min ≈ 3.3V + 0.35V (max dropout) ≈ 3.65V   (≈ 3.51V at 210 mV typ)
```

Compared with the very-low-dropout MCP1700, this raises the end-of-discharge
cutoff and therefore leaves a little usable LiPo capacity on the table at the
bottom of the discharge curve. That is an accepted trade for reliable operation
through Wi-Fi TX current spikes. (For a deep-sleeping e-paper device the average
current is tiny; the peak is the concern.)

### Decoupling (sized per the MCP1825S datasheet)

The MCP1825/MCP1825S is a low-noise LDO whose **stability requires a minimum
output capacitance of 1.0 µF** with an **ESR ≤ 1 Ω** (datasheet §3.4 & §4.3). It
is characterized with `CIN = COUT = 4.7 µF X7R ceramic` (datasheet AC/DC
Characteristics conditions). We follow the datasheet rather than reusing the
MCP1700 values:

| Cap | Value | Reason |
|-----|-------|--------|
| `C3` (input, `CIN`) | **4.7 µF X7R** | §4.4 recommends 1–4.7 µF for battery inputs |
| `C4` (output, `COUT`) | **4.7 µF X7R** | ≥ 1 µF minimum for stability; X7R ceramic has ~50 mΩ ESR, well inside the ≤ 1 Ω window; matches the datasheet characterization value |

A 22 µF maximum output cap is recommended by the datasheet; 4.7 µF is a safe,
hand-solderable choice.

**SOT-223 tab:** pin 2 is `GND` and is electrically the heat-spreader tab. Solder
the tab down to a `GND` copper pour for heat removal, per the datasheet package
drawing.

---

## 3. ESP32-S3-WROOM-1 (edge-castellated, hand-solderable)

The WROOM-1 is a certified module that already contains the crystal, antenna and
SPI flash. It is **edge-castellated**, so every required signal is on a
side-castellation solderable with a fine-tip iron.

- **Bottom GND/thermal pad is redundant.** Ground is also available on the
  castellations (pins 1 and 40) and the pad carries no unique signal. It may be
  **left unsoldered or served by a via** — no reflow/hot-air is needed to make
  the module functional. (For thermal/RF margin in a final product you can add a
  via and touch it with the iron, but it is optional.)
- Uses the **ESP32-S3-WROOM-1-N8** (quad SPI flash, no PSRAM). GPIO26–32 are
  internal to the module (SPI flash) and are not broken out. On PSRAM variants
  (`-N8R8` / `-N16R16V`) GPIO35–37 are consumed by the PSRAM; those variants are
  not used here, so GPIO35–37 are free and are exposed on the expansion header.
  GPIO47/48 also assume a non-`R16V` variant because `-N16R16V` uses 1.8 V I/O
  on those pins.

### Module support circuitry

| Function | Parts | Notes |
|----------|-------|-------|
| 3V3 decoupling | `C5` 100nF + `C6` 10µF | at the 3V3 pin |
| Reset (EN) | `R7` 10k pull-up to 3V3, `C7` 1µF to GND, `SW1` to GND | RC power-on reset + optional EN/RESET button. *Do not leave EN floating.* |
| Boot strap | `R8` 10k pull-up to 3V3 on **GPIO0**, `SW2` (BOOT) to GND | S3 download-boot strap is **GPIO0** |
| E-paper CS | `R14` 10k pull-up to 3V3 on **GPIO6** | keeps the panel deselected during reset/power-up |
| GPIO45 / GPIO46 | left at datasheet default | strapping pins — see §7 |
| GPIO3 | `R15` 10k pull-down (**DNP**) | optional strap pad; see §7 |

---

## 4. MCP73831 charger — no power-path (and why that is OK here)

The `MCP73831` (SOT-23-5, leaded, no exposed pad) is a **standalone linear
charger with no power-path / load-sharing**: the battery and the system load
share a single node (`VBAT`). There is no separate `SYS` output that can power
the load directly from USB while isolating the cell.

**Why acceptable for this device:** this is a deep-sleeping e-paper display whose
average load is very small. The cell stays connected to the LDO input at all
times; when USB is present the charger simply sources both the charge current and
the (tiny) system current from `VBAT`. There is no scenario where a large,
sustained load needs to run *and* charge from a dead battery, so the lack of a
power-path is a non-issue and buys us a smaller, cheaper, fully hand-solderable
part.

- **Charge current** is set by `R5` (PROG→GND): `I_REG = 1000V / R_PROG`
  (datasheet Eq. 5-1). `R5 = 4.7 kΩ → ≈ 213 mA`, a conservative ~0.43 C for a
  ~500 mAh cell (well under 0.5 C).
- Charge-regulation voltage: use the **`-2` (4.2 V)** option
  (`MCP73831T-2ACI/OT`).
- `C1` 4.7 µF on `VDD/VBUS` (input), `C2` 4.7 µF on `VBAT` (output).
- `STAT` (open-drain) drives a through-hole LED via `R6` 1 kΩ from 3V3
  (LED on = charging).

---

## 5. Power path (net summary)

```
USB-C VBUS ──► MCP73831 VDD (C1 4.7µF)
MCP73831 VBAT ──► VBAT node ──► JST-PH LiPo (C2 4.7µF)
VBAT ──► MCP1825S VIN (C3 4.7µF) ──► +3V3 (C4 4.7µF) ──► ESP32-S3 + e-paper
VBAT ──► R9/R10 (100k/100k divider, C8 100nF) ──► GPIO1 (ADC1_CH0) battery sense
```

USB-C sink configuration: `CC1`/`CC2` each get a **5.1 kΩ pull-down** (`R1`/`R2`)
to advertise a sink and pull the default USB power. `D+`/`D-` go through optional
**22 Ω** series resistors (`R3`/`R4`) to the module. An optional ESD TVS array
(`D1`, e.g. `USBLC6-2SC6`, SOT-23-6) sits on `VBUS`/`D+`/`D-`; it is marked **DNP
(do-not-populate)** and is the only fine-pitch part — populate it on a breakout
or omit it.

---

## 6. E-paper display (AES200200A00-1.54ENRS)

The 24-pin, 0.5 mm-pitch FPC is fine-pitch and **not** hand-solderable directly.
`J1` represents an **FPC-to-0.1" breakout / 24-pin 0.5 mm ZIF socket** — all
signals land on hand-solderable pads.

The display's on-FPC **DC/DC boost + charge pump** (which generates the gate and
source driving rails) is reproduced from the datasheet Reference Circuit (p.24)
using hand-solderable leaded parts:

| Ref | Part / value | Package | Function |
|-----|--------------|---------|----------|
| `L1` | 47 µH (CDRH2D18 / LDNP-470NC) | SMD inductor (leaded pads) | boost inductor, VCI→SW |
| `Q1` | Si1304BDL / NX3008NBK N-MOSFET | **SOT-23** | boost switch, gate = `GDR` |
| `R11` | 2.2 Ω 1% | 0805 | `RESE` current-sense resistor |
| `D3`,`D4`,`D5` | MBR0530 Schottky | SOD-123 | boost/charge-pump rectifiers |
| `C9` | 1 µF / 25 V | 0805 | flying capacitor (ref `C3`) |
| `C10` | 1 µF / 25 V | 0805 | `VGH` reservoir (ref `C2`) |
| `C11` | 1 µF / 25 V | 0805 | `VGL` reservoir (ref `C4`) |

Rail decoupling (per datasheet reference, all 1 µF; charge-pump rails 25 V):
`C12` VCI/VDDIO(+3V3), `C13` VDD(core), `C14` VSH1, `C15` VSH2, `C16` VSL,
`C17` VCOM.

Display power: **VCI, VDDIO and VPP are tied to +3V3** (VDDIO must equal VCI per
the datasheet; VPP is the OTP-programming supply, tied to VCI). **VDD** is the
core-logic rail regulated internally from VCI and only needs a 1 µF cap to VSS.
`BS1` (pin 8) is tied to **GND** to select **4-wire SPI** (datasheet Note 5-5).

Optional external I²C temperature sensor on `TSCL`/`TSDA` (display pins 6/7):
`R12`/`R13` 10 kΩ pull-ups to 3V3 (marked **DNP**) and a 4-pin header `J4`. Leave
unpopulated to use the controller's internal temperature sensor (datasheet says
these pins may be left **Open** when not in use).

---

## 7. Net-by-net connection list & final GPIO assignment

### ESP32-S3 ↔ e-paper (verified — no collision with USB or strapping pins)

| Display pin | Signal | Net | ESP32-S3 |
|-------------|--------|-----|----------|
| 13 | SCL (SCLK) | `EPD_SCLK` | **GPIO4** |
| 14 | SDA (MOSI) | `EPD_MOSI` | **GPIO5** |
| 12 | CS# | `EPD_CS` | **GPIO6** (`R14` 10 kΩ pull-up) |
| 11 | D/C# | `EPD_DC` | **GPIO7** |
| 10 | RES# | `EPD_RST` | **GPIO8** |
| 9 | BUSY | `EPD_BUSY` | **GPIO9** (input) |
| 8 | BS1 | `GND` | tie low → 4-wire SPI |
| 6 / 7 | TSCL / TSDA | `EPD_TSCL` / `EPD_TSDA` | optional I²C temp header (`J4`), else Open |

`GPIO4–7` are the prompt-specified SPI pins; `RES`/`BUSY` use the next free
`GPIO8`/`GPIO9`. None collide with USB (GPIO19/20) or the strapping pins
(GPIO0/45/46/3).

### Reserved / special pins

| Signal | ESP32-S3 | Notes |
|--------|----------|-------|
| USB D- | **GPIO19** | via `R4` 22 Ω to USB-C `D-` |
| USB D+ | **GPIO20** | via `R3` 22 Ω to USB-C `D+` |
| BOOT strap | **GPIO0** | 10k pull-up + BOOT button |
| Battery sense | **GPIO1** (ADC1_CH0) | VBAT ÷2 divider |
| UART0 TXD/RXD | **GPIO43 / GPIO44** | optional console header `J5` |
| VDD_SPI strap | **GPIO45** | left at default (weak pull-down = 0); NC |
| ROM-msg / boot strap | **GPIO46** | left at default (weak pull-down = 0); NC |
| JTAG-source strap | **GPIO3** | optional `R15` 10 kΩ pull-down (**DNP**); `STRAP_IO3` |

Strapping-pin defaults are from the ESP32-S3-WROOM-1 datasheet Table 4-1
(GPIO0 = weak pull-up 1, GPIO3 = floating, GPIO45/46 = weak pull-down 0).

### Power / battery nets

| Net | Members |
|-----|---------|
| `VBUS` | USB-C VBUS, MCP73831 VDD, `C1`, TVS `D1`, `#FLG1` |
| `VBAT` | MCP73831 VBAT, MCP1825S VIN, JST `J3`, `C2`, `C3`, `R9` (sense) |
| `+3V3` | MCP1825S VOUT, module 3V3, display VCI/VDDIO/VPP, `C4/C5/C6/C12`, `R7/R8/R14`, header power |
| `GND` | common ground / all decoupling returns / SOT-223 & module GND pads / `#FLG2` |

`#FLG1`/`#FLG2` are `PWR_FLAG`s (not real parts) marking `VBUS`/`GND` as
externally driven for ERC.

### Spare GPIO expansion header (`J6`, 2×12)

Exposes 3V3, GND and spare GPIOs `IO2, IO10–IO18, IO21, IO35–IO42, IO47, IO48`
for future peripherals.

---

## 8. Bill of Materials

**PACKAGE / mounting column:** every part is THT, hand-solderable leaded SMD
(SOT-23 / SOT-223 / SOD-123 / 0805 / TO-92-class), a castellated module, or a
breakout adapter. **No exposed-pad (QFN/DFN) parts. No reflow required.**

| Ref | Value / Part number | Package / mounting |
|-----|--------------------|--------------------|
| U1 | ESP32-S3-WROOM-1-N8 (quad flash, no PSRAM) | **Castellated module** (bottom pad optional) |
| U2 | MCP73831T-2ACI/OT (4.2 V) | **SOT-23-5** (hand-solderable SMD) |
| U3 | **MCP1825S-3302E/DB** (3.3 V, 500 mA LDO) | **SOT-223-3** (hand-solderable SMD, tab = GND) |
| Q1 | Si1304BDL / NX3008NBK N-MOSFET | **SOT-23** |
| D1 | USBLC6-2SC6 ESD TVS *(optional, DNP)* | SOT-23-6 (on breakout / omit) |
| D2 | LED (charge status) | **THT** 3 mm LED |
| D3,D4,D5 | MBR0530 Schottky | **SOD-123** (hand-solderable SMD) |
| L1 | 47 µH (CDRH2D18 / LDNP-470NC) | 1210 SMD inductor |
| R1,R2 | 5.1 kΩ (USB CC pull-downs) | 0805 |
| R3,R4 | 22 Ω (USB D+/D- series) | 0805 |
| R5 | 4.7 kΩ (charge-current PROG) | 0805 |
| R6 | 1 kΩ (STAT LED) | 0805 |
| R7,R8 | 10 kΩ (EN, BOOT pull-ups) | 0805 |
| R9,R10 | 100 kΩ (battery-sense divider) | 0805 |
| R11 | 2.2 Ω 1% (RESE sense) | 0805 |
| R12,R13 | 10 kΩ (I²C temp pull-ups, **DNP**) | 0805 |
| R14 | 10 kΩ (EPD CS pull-up) | 0805 |
| R15 | 10 kΩ (GPIO3 pull-down, **DNP**) | 0805 |
| C1,C2 | 4.7 µF (charger in/out) | 0805 X7R |
| C3,C4 | 4.7 µF (LDO in/out) | 0805 X7R |
| C5 | 100 nF (module decoupling) | 0805 |
| C6 | 10 µF (module bulk) | 0805 X7R |
| C7 | 1 µF (EN RC) | 0805 |
| C8 | 100 nF (battery-sense filter) | 0805 |
| C9,C10,C11 | 1 µF / 25 V (boost flying + VGH/VGL) | 0805 X7R |
| C12 | 1 µF (display VCI/VDDIO) | 0805 |
| C13 | 1 µF (display VDD core) | 0805 |
| C14,C15,C16,C17 | 1 µF / 25 V (VSH1/VSH2/VSL/VCOM) | 0805 X7R |
| J1 | AES200200A00 24-pin 0.5 mm FPC | **FPC-to-0.1" breakout / 0.5 mm ZIF socket** |
| J2 | USB-C receptacle (2.0, sink) | **THT / hand-solderable receptacle or breakout** |
| J3 | LiPo battery | **JST-PH 2-pin** THT connector |
| J4 | I²C temp sensor *(optional)* | **THT** 1×4 0.1" header |
| J5 | UART console | **THT** 1×4 0.1" header |
| J6 | GPIO expansion | **THT** 2×12 0.1" header |
| SW1,SW2 | EN/RESET, BOOT buttons | tactile switch |

---

## 9. Assembly / soldering notes

- **No reflow, no hot-air, no solder stencil is required.** Every part is
  attachable with a fine-tip soldering iron.
- Solder the **ESP32-S3-WROOM-1-N8** via its edge castellations (drag-solder). Its
  **bottom GND/thermal pad is redundant and may be left unsoldered** (GND is on
  castellations 1 & 40) — no reflow needed.
- Solder the **MCP1825S SOT-223 tab (pin 2, GND)** flat onto a GND copper pour
  for heat-spreading.
- SOT-23 / SOT-23-5 / SOD-123 / 0805 parts hand-solder easily; tin one pad,
  place the part, then solder the remaining pins.
- The **only** fine-pitch SMT part is the optional ESD TVS `D1` — it is DNP and
  may be placed on a breakout or omitted entirely.
- The e-paper FPC connects through an FPC-to-0.1" breakout / 0.5 mm ZIF socket,
  so no fine-pitch FPC soldering is needed on this board.

## 10. Status / not included

- **PCB layout is not included yet** — this is a schematic-level deliverable,
  but every real (BOM) component now has a KiCad standard-library footprint
  assigned, so *Update PCB from Schematic* runs without "no footprint assigned"
  errors. Chip passives are all **0805** to stay hand-solderable, the MBR0530
  Schottkys use `D_SOD-123` and `L1` uses `L_1210_3225Metric`; `gen_sch.py`
  fails loudly if a BOM component is left without one.
- `J2` (USB-C) is assigned `Connector_USB:USB_C_Receptacle_GCT_USB4085`, but its
  simplified logical 9-pin symbol does **not** map 1:1 to the receptacle's
  A/B-numbered pads — the pad assignment must be verified (or the stock KiCad
  USB-C symbol substituted) at layout time. `D1` (USBLC6-2SC6) uses the real
  SOT-23-6 pinout (1/6=I/O1, 3/4=I/O2, 2=GND, 5=VBUS) so it maps correctly to
  `SOT-23-6`.
- Component placement in the schematic is auto-generated and rough; connectivity
  is by global label and is correct (verified by KiCad 8 ERC + netlist export).

## Regenerating

```
cd hardware
python3 gen_sch.py            # regenerates .kicad_sch, epaper.kicad_sym, sym-lib-table
kicad-cli sch erc epaper-display.kicad_sch          # -> 0 violations
kicad-cli sch export netlist epaper-display.kicad_sch
```
