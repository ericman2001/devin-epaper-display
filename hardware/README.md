# E-Paper Display — Hardware (KiCad schematic)

Battery-powered 1.54" e-paper display built around the **ESP32-C6-WROOM-1-N8**
module — a 32-bit **RISC-V** single-core part with Wi-Fi 6, Bluetooth LE 5.3 and
802.15.4 (Thread/Zigbee). This directory contains a **schematic only** — no PCB
layout yet, but every component carries a footprint.

> ⚠️ **`U1` needs Espressif's KiCad library.** Stock KiCad has no
> `ESP32-C6-WROOM-1` footprint — its `RF_Module` library carries only
> `ESP32-C6-MINI-1` — so `U1` is drawn as `Espressif:ESP32-C6-WROOM-1`. Install
> the *Espressif KiCad Library* from KiCad's **Plugin and Content Manager**
> before opening the schematic or the footprint will not resolve. Every other
> footprint on the board comes from the stock libraries as before.

Files:

| File | Purpose |
|------|---------|
| `epaper-display.kicad_pro` | KiCad 8 project |
| `epaper-display.kicad_sch` | Schematic (KiCad 7/8 S-expression, `kicad_sch`) |
| `epaper.kicad_sym` | Project symbol library (referenced by the schematic) |
| `sym-lib-table` | Maps the `epaper` library nickname to `epaper.kicad_sym` |
| `epaper-display-schematic.pdf` | Rendered schematic (**stale**, see note below) |
| `gen_sch.py` | Generator that produces the schematic/library from the netlist definition |

Connectivity is expressed with **global labels**, so the netlist is correct even
though the auto-generated component placement is rough. Re-open in KiCad and
rearrange/route as desired.

> ⚠️ **`epaper-display-schematic.pdf` is stale** — it still shows the
> ESP32-S3 revision of this board and has not been re-rendered, because
> `kicad-cli` was not available where these changes were made. Regenerate it (and re-run ERC) with the
> commands in [Regenerating](#regenerating) before relying on it. The
> `.kicad_sch` is the current source of truth; `gen_sch.py` generates it and
> self-checks the netlist on every run.

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
                  +--> 0R  --> D-/D+ (GPIO12 / GPIO13, native USB-Serial/JTAG)
                  |
                  v
        MCP73831 (SOT-23-5)  Li-ion/LiPo linear charger  (no power-path)
                  |  VBAT
                  v
        single-cell LiPo (JST-PH)  <---- system battery node (VBAT) ---->  TLV75733P
                                                                              |  (SOT-23-5, 3.3V/1A LDO, IQ 25uA)
                                                                              v
                                                                            +3V3 rail
                                                                              |
                        +-----------------------------------------------------+
                        |                                                     |
              ESP32-C6-WROOM-1-N8 (3V3)                        AES200200A00 e-paper (VCI/VDDIO)
              + 100nF + 10uF decoupling                       + discrete DC/DC boost & charge pump
                                                              (L1/Q1/D3-D5, see §6)
```

- **Power in:** one USB-C receptacle provides both **VBUS (charging)** and the
  **native USB** programming/serial link.
- **Charging:** `MCP73831` charges the LiPo. Its `VBAT` pin is the system
  battery node and directly feeds the regulator (see §4 — no power-path).
- **Regulation:** `TLV75733PDBVR` (fixed 3.3V, 1 A, SOT-23-5, `IQ` 25 µA)
  generates the `+3V3` rail that powers the module and the display. See §2 for
  why this is linear rather than a switcher.
- **Programming/serial:** ESP32-C6 native USB-Serial/JTAG on **GPIO12 (D-)** and
  **GPIO13 (D+)**. No external USB-UART bridge required. UART0 (GPIO16/17) is
  also broken out on a header for an optional console.
- **Expansion:** `J6`, a 2×4 0.1" header: 3V3/GND, an I²C pair with DNP
  pull-ups, one pin that is both **ADC1** and deep-sleep-wake capable, and one
  spare GPIO. That is four GPIOs, down from fifteen on the S3 revision — see §7
  for the pin arithmetic that forces it.

---

## 2. Regulator choice — TLV75733P (linear, low-IQ)

The ESP32-C6's Wi-Fi TX current peaks at **382 mA** (802.11b, 1 Mbps DSSS
@20.5 dBm, module datasheet Table 6-4). BLE and 802.15.4 peak lower — 309 mA and
302 mA respectively at 19 dBm — so 802.11b is the sizing case. The regulator has
to cover that burst on a rail that is otherwise drawing microamps.

**This went up, not down, with the move to the C6:** the S3 peaked at 355 mA, so
the burst the regulator has to serve grew by 27 mA (+8 %). Everything below still
holds with margin — the `TLV75733P` is a 1 A part — but the two rejected
candidates are rejected harder now, not less.

Two earlier revisions got this wrong in opposite directions: an `MCP1700-3302E/TO`
(250 mA) that browned out during transmit, then an **`MCP1825S-3302`** (500 mA,
SOT-223) that handled the burst but drew **120 µA typ / 220 µA max of quiescent
current** — roughly 17× the ESP32-C6's own deep-sleep draw, which made the
regulator the entire standby budget on a device that is asleep 99.98 % of the
time.

This revision uses the **`TLV75733PDBVR`** (SOT-23-5, 1 A, `IQ` 25 µA).

### Why linear and not a switcher

The intuition that a buck converter saves power is right in general and wrong
here, for four separate reasons:

1. **The duty cycle makes efficiency almost irrelevant.** Four wake cycles a day
   at ~5 s each is ~20 s of activity in 86 400 — about **0.023 %**. An LDO's
   efficiency is `VOUT/VIN`: 79 % at 4.2 V, 89 % at 3.7 V, 97 % near 3.4 V, so
   call it ~85 % averaged over the discharge curve. A good buck might reach
   90–93 %. Applied to ~1.8 mWh/day of active energy, that gap is worth about
   **0.1 mWh/day** — roughly 2 % of the total budget, and far less than the
   regulator's own `IQ` contributes.
2. **A plain buck cannot even do the job.** A single LiPo runs 4.2 V down to
   3.0 V, which *straddles* the 3.3 V output. Below ~3.4 V there is nothing left
   to buck. Covering the full cell range needs a **buck-boost**, which is
   bigger, costlier, and typically has 25–50 µA of quiescent current — so it
   wins nothing on the axis that actually matters.
3. **The good low-`IQ` switchers are unbuildable here.** The parts with genuinely
   spectacular numbers (TPS62840: 60 nA `IQ`, 750 mA) ship in SOT-583 or WSON —
   fine-pitch, exposed-pad, reflow. That breaks the constraint the whole BOM is
   built around: hand-solderable with a fine-tip iron, no reflow, no hot air.
4. **Switching noise, next to the wrong neighbours.** A switching node would sit
   alongside the panel's own boost converter and a battery-sense divider with a
   500 kΩ source impedance, on a board that has not been laid out yet.

Since standby dominates, **`IQ` is the only regulator figure of merit that moves
the needle** — and low `IQ` is something a linear part supplies perfectly well.

### Where the returns stop

Estimated life on the target cell (a 300 mAh LiHV pack charged to 4.20 V,
~930 mWh usable — see §4), at 4 updates/day:

| Regulator | `IQ` | Total standby | Est. life |
|---|---|---|---|
| MCP1825S (old) | 120 µA | ~136 µA | ~2 months |
| **TLV75733P** | **25 µA** | **~41 µA** | **~5 months** |
| TPS7A0533 (200 mA) | 1 µA | ~17 µA | ~6 months |

Dropping 120 → 25 µA roughly doubles the achievable life. Chasing 25 → 1 µA
gains less than it looks: the cell's own self-discharge and the panel's 1–5 µA
sleep current start to dominate, and the only SOT-23-5 parts down there
(TPS7A05) top out at **200 mA**, which cannot serve a 382 mA TX burst. 25 µA is
the knee of the curve.

### TLV75733P specifics (SBVS322C)

| Parameter | Value | Source |
|---|---|---|
| `VIN` range | 1.45 – **5.5 V** | §5.5 |
| `IGND` (quiescent) | 25 µA typ, 31 µA max @25 °C, 33 µA max to +85 °C | §5.5 |
| Dropout | **425 mV max at 1 A** (3.3 V out) | §1 |
| Current limit | 1.2 A min / 1.55 A typ | §5.5 |
| `COUT` | ≥ 0.47 µF, **≤ 200 µF**, X5R/X7R | §7.1.1 |
| `CIN` | ≥ 1 µF | §7.1.1 |
| `RθJA` (DBV, JEDEC) | **231.1 °C/W** — no thermal pad | §5.4 |

**Dropout improves over the MCP1825S.** §7.1.2 states that `VDO` scales linearly
with output current (the pass element is a PMOS acting as a resistor in
dropout), so 425 mV at 1 A implies ~212 mV max at 500 mA, against the
MCP1825S's 350 mV max. That moves the end-of-discharge floor down:

```
VBAT_min ≈ 3.3V + 0.21V ≈ 3.51V     (was ≈ 3.65V with the MCP1825S)
```

which recovers a little of the usable capacity the previous revision gave away
at the bottom of the curve.

**Thermal is the one thing that got worse, and it is a deliberate trade.** The
MCP1825S's SOT-223 tab was a genuine heat spreader; the DBV package has no
thermal pad and `RθJA` = 231 °C/W. Worst case is a full battery into a full
load: `(4.2 − 3.3) V × 0.5 A = 0.45 W`, which is ~104 °C of rise at steady
state. That is fine here *only* because the load is a ~5 second burst at 0.023 %
duty cycle and never reaches steady state — realistic sustained active current
is ~150 mA (0.135 W, ~31 °C rise). Two consequences:

- Give `U3` a decent copper pour anyway — see **§10**, which works the numbers
  for every load case and explains why copper beats a stick-on heatsink here.
- **Do not draw a sustained 500 mA from `+3V3` through the `J6` header.** The
  part will current-limit and thermally protect itself, but it is not a
  continuous half-amp supply in this package. If a future revision needs that,
  the pin-compatible **DYD** package (same SOT-23-5 pinout, exposed pad,
  `RθJA` 92.5 °C/W) is the answer — at the cost of needing reflow.

**One margin reduction worth noting:** `VIN(max)` drops from the MCP1825S's 6.0 V
to **5.5 V**. `VBAT` is regulated to 4.2 V by the charger so this is never
approached in normal operation, and even a shorted-pass-transistor failure in
`U2` would put only ~5 V on it — but the abuse headroom is thinner than it was.

### The regulator is a drop-in socket

`U3`'s symbol is a generic `LDO_SOT23_5` with the standard **1=IN, 2=GND, 3=EN,
4=NC, 5=OUT** pinout (verified against KiCad 8.0.9's `Regulator_Linear`
library). `TLV75733PDBVR`, `AP2112K-3.3TRG1`, `XC6220B331MR` and `TPS7A0533PDBV`
all drop into these pads unchanged, so the part can be re-specced on
availability without touching the schematic. `EN` is tied to `IN` so the rail is
always on — **it must not be left floating.**

### Decoupling

| Cap | Value | Reason |
|-----|-------|--------|
| `C3` (input, `CIN`) | 4.7 µF X7R 0805 | §7.1.1 asks for ≥ 1 µF |
| `C20` (input bulk) | 100 µF X5R 1206 | high-impedance source / large fast load steps (§7.1.1) |
| `C4` (output, `COUT`) | 4.7 µF X7R 0805 | ≥ 0.47 µF for stability |
| `C18` (output bulk) | 47 µF X5R 1206 | burst reservoir — see §5.1 |

---

## 3. ESP32-C6-WROOM-1 (edge-castellated, hand-solderable)

The WROOM-1 is a certified module that already contains the 40 MHz crystal,
antenna and SPI flash. It is **edge-castellated** — 14 pads per long edge on a
1.27 mm pitch, 1.5 × 0.9 mm each — so every required signal is on a
side-castellation solderable with a fine-tip iron.

- **Same outline as the S3 module it replaces.** 18.0 × 25.5 × 3.1 mm (datasheet
  Figure 10-1), identical to the ESP32-S3-WROOM-1, so board outline, keepout and
  antenna clearance are unchanged. The **pads are not** compatible: 29 pins
  against 41, in a different order. This is a footprint change, not a drop-in.
- **Bottom GND/thermal pad is redundant.** Ground is also available on the
  castellations (pins 1 and 28) and the pad carries no unique signal. It may be
  **left unsoldered or served by a via** — no reflow/hot-air is needed to make
  the module functional. (For thermal/RF margin in a final product you can add a
  via and touch it with the iron, but it is optional.)
- Uses the **ESP32-C6-WROOM-1-N8** (8 MB quad SPI flash). GPIO24–30 are internal
  to the module (SPI flash) and are not broken out, and GPIO14 is not bonded out
  of the package — module pin 22 is a real `NC`. Everything else is available:
  **23 GPIOs**, and this design uses all 23.
- **The PSRAM caveats from the S3 revision are gone.** There is no PSRAM variant
  of the C6-WROOM-1 — the series is N4/N8/N16, flash only (datasheet Table 1-1) —
  so there are no pins whose availability depends on which module was ordered,
  and no 1.8 V-I/O variant to avoid.
- **RISC-V, single core, up to 160 MHz** (the S3 was dual-core Xtensa at
  240 MHz). Radios gained: Wi-Fi 6 (802.11ax), Bluetooth LE 5.3, and 802.15.4 for
  Thread/Zigbee. For a display that wakes four times a day this is a net win on
  the axis that matters — see the thermal table in §10, where the sustained
  compute case drops from 108 mA to 38 mA.

### Module support circuitry

| Function | Parts | Notes |
|----------|-------|-------|
| 3V3 decoupling | `C5` 100nF + `C6` 10µF | at the 3V3 pin |
| Reset (EN) | `R7` 10k pull-up to 3V3, `C7` 1µF to GND, `SW1` to GND | RC power-on reset + optional EN/RESET button. *Do not leave EN floating.* |
| Boot strap | `R8` 10k pull-up to 3V3 on **GPIO9**, `SW2` (BOOT) to GND | C6 download-boot strap is **GPIO9** (the S3's was GPIO0) |
| Boot strap 2 | `R28` 10k pull-up to 3V3 on **GPIO8** (**populated**) | GPIO8 must read 1 for download boot — required, see §7 |
| E-paper CS | `R14` **100k** pull-up to 3V3 on **GPIO21** | keeps the panel deselected during reset/power-up |
| E-paper reset | `R16` **100k** pull-down to GND on **GPIO19** | holds active-low `RES#` asserted while the ESP32 is in reset; the panel stays in reset until firmware drives GPIO19 high, alongside the `EN`/`SW1` reset RC |
| GPIO15 | `R15` 10k pull-**up** (**populated**) | JTAG-source strap; required, not optional — see §7 |
| GPIO4 / GPIO5 | button pull-ups `R17`/`R18` latch them high | SDIO-slave clock-edge straps; inert here — see §7 |

`R14`/`R16` are 100 kΩ rather than 10 kΩ: they only ever have to overcome a CMOS
input's leakage, and at 10 kΩ each would sink 330 µA whenever firmware drives
the pin against the resistor — which is a lot on a board whose deep-sleep budget
is measured in single-digit microamps.

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
  (datasheet Eq. 5-1). `R5 = 10 kΩ → 100 mA`.
- Charge-regulation voltage: use the **`-2` (4.2 V)** option
  (`MCP73831T-2ACI/OT`).
- `C1` 4.7 µF on `VDD/VBUS` (input), `C2` 4.7 µF on `VBAT` (output).
- `STAT` (tri-state on the '831) drives a through-hole LED via `R6` 1 kΩ **from
  `VBUS`** (LED on = charging).

### Why 100 mA and not 213 mA

The earlier `R5 = 4.7 kΩ` (213 mA) was thermally marginal in a SOT-23-5. The
datasheet gives θJA = **230 °C/W** on minimum copper (130 °C/W with a large
pour), and the worst case is the transition out of preconditioning:

```
P = (VDD_max − VPTH_min) × I_REG = (5.5V − 2.8V) × 213mA ≈ 0.57 W
ΔT = 0.57 W × 230 °C/W ≈ 132 °C     → thermal regulation folds the current back
```

At 100 mA the same worst case is `0.27 W → 62 °C rise`, which stays out of
thermal regulation even on modest copper. A 100 mA charge is **0.33 C** for the
300 mAh cell this design targets — comfortably inside the 0.5 C that small pouch
cells typically permit — and takes about 3 h of constant-current plus taper,
call it 4 h to full. This is a device that sits on a desk and sleeps, so the
slower charge costs nothing and the charger no longer runs hot.

### Why the STAT LED returns to `VBUS`, not `+3V3`

This matters more than it looks. The datasheet's own application circuit
(Fig. 6-1) puts `RLED` between **VDD** and `STAT`. Returning it to the regulated
`+3V3` rail instead means that when USB is absent — i.e. almost always — the LED
is still forward-biased *from the battery* into the `STAT` pin, because `STAT`
is high-Z in shutdown. That current flows through the pin's ESD structure into
the charger's `VDD` node, back-feeding both `C1` and the **USB-C `VBUS`
contact** off the cell, and it violates the absolute maximum rating
*"All Inputs and Outputs w.r.t. VSS: −0.3 to (VDD+0.3)V"*. The steady-state
current is small (VDD floats up to ~0.8 V and the charger stays below UVLO), but
a board that drives its own `VBUS` pin from the battery is not a board you want
to ship. Referencing `R6` to `VBUS` makes the whole path disappear when USB is
unplugged.

### Battery protection — on-board DW01A + FS8205A

The board carries its own **1S protection circuit** (`U4` DW01A + `Q2` FS8205A),
wired exactly as the DW01A datasheet application circuit on p.9 draws it. `J3`
is therefore the **raw cell**, not a protected pack:

```
   cell +  ──┬──────────────────────────────────────────────►  VBAT (= B+ = P+)
             │                    R24 100R
             └──────────────/\/\/──────┬── VDD ┐
                                        │        │  U4 DW01A
                          C21 100nF ════╡        │
                                        │        │   DO ──► G1
   cell −  ──┬─────────────────────────┴── VSS ┘   CO ──► G2
             │                                       VM ──┬──/\/\/── GND
             │                                            │  R25 1k
             └──► S1 ┤ Q2 FS8205A ├ S2 ──────────────────┴─────────►  GND (= P−)
                     └── D1/D2 common ──┘
```

The high side is never switched; both FETs sit in the **low side** between the
cell's negative terminal (`BATT_NEG`) and board `GND`. Half 1 is discharge
control (gate `DO`, source `B−`), half 2 is charge control (gate `CO`, source
`P−`). That pairing is fixed by the DW01A, which turns the discharge FET off by
driving `DO` to `VSS` and the charge FET off by driving `CO` to `VM` — each gate
must be referenced to its own source.

| Protection | Threshold | Delay | Source |
|---|---|---|---|
| Overcharge | 4.30 V ±50 mV (restore 4.10 V) | 110 ms | DW01A p.1, p.3 |
| Over-discharge | 2.50 V ±75 mV (recover 2.90 V) | 55 ms | DW01A p.1, p.3 |
| Over-current | 0.15 V ±20 mV across the FETs | 7 ms | DW01A p.1, p.3 |
| Short circuit | `VSHORT` on `VM` | 200–600 µs | DW01A p.4 |

`Q2` adds `2 × 20.5 mΩ` (typ, `VGS` = 4.5 V) to the ground return — about 41 mΩ,
or 20 mV at a 500 mA burst. Negligible, and already accounted for in the sag
table above. Its 6 A rating is 12× what this board draws.

#### `Q2` pin numbering

Neither FS8205A datasheet in `components/` carries a pin-number-to-function
table, and KiCad has no FS8205A symbol, so this took two documents to pin down:

| Source | What it gives |
|---|---|
| `fs8205a.pdf` (Evvosemi) | schematic only (D1/G1/S1, D2/G2/S2, common drain); package drawing numbers pins but labels no functions |
| `fs8205a-techpublic.pdf` | **"Package and Pin Configuration" linking function to package position** |

The Tech Public drawing is the one that resolves it:

```
        pin 6  G1        pin 5  D1/D2      pin 4  G2
        pin 1  S1        pin 2  D1/D2      pin 3  S2
```

Each half occupies one **end** of the package — FET1 is `S1`/`G1` at pins 1/6,
FET2 is `S2`/`G2` at pins 3/4 — with the common drain brought out on the two
**middle** pins. A symmetric leadframe, which is a good sign in itself.

> **This is not the commonly-quoted "8205A" mapping** (`1=S1 2=G1 3=S2 4=G2
> 5=D2 6=D1`), which puts a gate in the middle of the source row. An earlier
> revision wired that version and it was wrong: `PROT_DO` would have been driven
> into a drain and `G1` tied to the drain node, so the protection would have
> silently not worked. If you are cross-referencing other 8205A designs, expect
> to see the other mapping and do not assume it applies.

Worth one bench check when the parts arrive, since it costs nothing: the two
pins shorted to each other are the drains; in diode mode, red probe on a pin and
black on the drain node reading ~0.5–0.7 V identifies a **source**; the
remaining two pins are the **gates**.

**`U4` costs 2.0 µA typ / 6.0 µA max** (`IDD`, datasheet p.4), which is why the
standby budget below is *better* than the external-protection-board variant: the
2 µA replaces a ~3 µA estimate, and removing `D6` (below) saves another ~3 µA.

#### Why `D6` was removed

Earlier revisions carried an SS14 reverse-polarity crowbar across the battery
input. It has been **deleted**, and that is a deliberate safety decision rather
than a simplification.

Its entire rationale was *"short a reversed cell and let the pack's protection
PCM interrupt the fault"*. With the protection moved on-board, a reversed
connector is applied **upstream** of `U4`/`Q2` — so there is nothing left to
clear the fault. An 80C 300 mAh cell can source roughly **24 A** into a 1 A
diode. That turns the board's designated short-circuit path from a safeguard
into a fire risk.

**The residual risk is real and is not papered over: this board now has no
reverse-polarity protection.** Plugging the cell in backwards will reverse-bias
`U4` (its `VDD` sits 3.8 V below `VSS`, against a −0.3 V absolute maximum,
current-limited to ~31 mA by `R24`) and will probably destroy it, possibly `Q2`
too. The mitigations are the keyed connector and **checking polarity with a
meter before the first plug-in** — see the assembly notes. Losing a ten-cent
DW01A to a reversed connector is an acceptable failure; a 24 A short through a
1 A diode is not.

#### One corner worth knowing about

The charger and the overcharge threshold are close enough that their tolerance
bands can touch:

| | Min | Typ | Max |
|---|---|---|---|
| `U2` MCP73831**-2** `VREG` | 4.168 V | 4.200 V | 4.232 V |
| `U4` DW01A `VOC` @ 25 °C | 4.250 V | 4.300 V | 4.350 V |
| `U4` DW01A `VOC`, −40…85 °C | 4.220 V | 4.300 V | 4.380 V |

At 25 °C the worst case leaves 18 mV of margin. Across the full temperature
range the bands can **overlap by 12 mV**, so an extreme corner could trip
overcharge protection before the charger terminates normally. Typical parts sit
100 mV apart and this never happens.

It matters because of a DW01A quirk (datasheet p.6): once in overcharge
protection, **if a charger is still present the DW01A will not restore even when
the cell falls below `VOCR`** — the charger has to be unplugged first. So the
symptom would be "charging stopped and won't resume until I unplug USB", not
anything damaging. This is also a second, independent reason not to fit the
4.35 V `-3` charger variant: it would trip overcharge protection *by design*.

### Cell selection — Turnigy BoltX LiHV 300 mAh

The target cell is a **Turnigy BoltX LiHV 1S 300 mAh 3.8 V 80C** whoop/micro-drone
pack with a PH2.0 lead. Drone packs ship as **bare cells** — maximum discharge
rate, minimum weight, no protection circuit, because the flight controller
normally handles low-voltage cutoff. That is why the 1S protection lives on this
board (`U4`/`Q2`, above) rather than in the pack.

**Charge to 4.20 V, not 4.35 V — keep `U2` as the `-2` option.** LiHV chemistry
is rated for a 4.35 V charge, and the MCP73831 does offer a 4.35 V variant
(`MCP73831T-3ACI/OT`, datasheet §1.0 `VREG`). Do *not* fit it here: standard
DW01A-based protection boards cut off overcharge at about **4.3 V**, so a 4.35 V
charger would fight the protection circuit. Charging an HV cell to 4.20 V is
entirely safe — it is an undercharge — and costs roughly 13 % of the nameplate
capacity. It also meaningfully improves calendar life, which matters on a device
that sits near full charge for months at a time.

**The 80C rating is wildly overspecified for this load, and that is fine.** We
draw 382 mA, about 1.3C. The one thing it does buy is very low internal
resistance, which removes the voltage-sag concern that a generic 300 mAh cell
would have created. Cell OCV needed = 3.3 V + `U3` dropout (0.425 V/A) + sag:

| Cell | Load | Sag | Cell OCV needed |
|---|---|---|---|
| Generic 300 mAh, 300 mΩ | TX 382 mA | 115 mV | 3.58 V |
| Generic 300 mAh, 300 mΩ | TX + refresh 530 mA | 159 mV | 3.68 V |
| **80C cell + `Q2`, ~75 mΩ** | **TX 382 mA** | **29 mV** | **3.49 V** |
| **80C cell + `Q2`, ~75 mΩ** | **TX + refresh 530 mA** | **40 mV** | **3.57 V** |

The C6's 27 mA higher TX peak moves each of these by 10–20 mV; it does not
change the conclusion. Even the combined TX-plus-refresh case needs only 3.57 V
of open-circuit voltage instead of 3.68 V. Serialising Wi-Fi and panel refresh (fetch,
disconnect, then process and refresh) is still the right firmware structure, but
it is no longer load-bearing for the power budget — it is just good practice.

### Energy budget

| | |
|---|---|
| Nameplate | 300 mAh × 3.8 V = 1140 mWh *(rated at a 4.35 V charge)* |
| Charged to 4.20 V | ~87 % → ~261 mAh |
| Usable to a ~3.4 V firmware cutoff | ~248 mAh ≈ **930 mWh** |

Standby, with the protection board's own draw included:

| Contributor | Current |
|---|---|
| `U3` `IGND` | 25.0 µA |
| ESP32-C6 deep sleep (RTC timer + LP memory on) | 7.0 µA |
| Panel deep sleep | 5.0 µA |
| `R9`/`R10` divider (1M/1M) | 2.1 µA |
| `U4` DW01A `IDD` (typ; 6.0 µA max) | 2.0 µA |
| **Total** | **~41 µA → 3.75 mWh/day** |

Slightly *better* than the external-protection-board variant this replaced: the
DW01A's 2 µA typ undercuts the ~3 µA budgeted for an outboard PCB, and deleting
`D6` saves another ~3 µA of Schottky leakage.

| Updates/day | Budget | Est. life |
|---|---|---|
| 1 | 5.1 mWh/day | ~184 days |
| **4** | **6.4 mWh/day** | **~144 days** |
| 12 | 10.1 mWh/day | ~92 days |
| 24 (hourly) | 15.6 mWh/day | ~59 days |

So roughly **4½–5 months** at 4 updates/day. Past ~4 updates/day the Wi-Fi wake
cycles dominate and cadence is the only lever that matters.

### Before first plug-in

- **Verify PH2.0 polarity with a meter.** This is a drone pack, and its housing
  wiring need not match the Adafruit/SparkFun convention that `J3`'s footprint
  assumes. There is no reverse-polarity protection left on the board, so this
  check is the only thing standing between a mis-wired lead and a dead `U4`.
- **Set the firmware cutoff around 3.4 V**, well above `U4`'s 2.50 V
  over-discharge threshold. The protection board is the last line of defence
  against a ruined cell, not the normal operating limit.
- Charging at 100 mA (`R5` = 10 kΩ) is 0.33 C — gentle, ~4 h to full, and no
  change from the current BOM.



---

## 5. Power path (net summary)

```
USB-C VBUS ──► MCP73831 VDD (C1 4.7µF, D7 SMAJ5.0A TVS)
MCP73831 VBAT ──► VBAT node ──► J3 cell B+ (C2 4.7µF)
J3 cell B− ──► U4/Q2 1S protection (DW01A + FS8205A) ──► GND
VBAT ──► TLV75733P IN/EN (C3 4.7µF + C20 100µF) ──► +3V3 (C4 4.7µF + C18 47µF) ──► ESP32-C6 + e-paper
VBAT ──► R9/R10 (1M/1M divider, C8 100nF) ──► GPIO0 (ADC1_CH0) battery sense
```

### 5.1 Rail buffering

The module datasheet lists `IVDD ≥ 0.5 A` as a *recommended operating
condition* (Table 6-2), and an 802.11b TX burst is **382 mA peak** (Table 6-4).
`U3` is rated at 1 A with a 1.2 A minimum current limit, so the regulator itself
has headroom; the capacitors are there to cover the transient while its loop
responds.

The bulk sits on the **output**, where the load transient actually is. (An
earlier revision was forced to put it on `VBAT` instead, because the MCP1825S
capped `COUT` at 22 µF. TLV757P §7.1.1 allows *"no greater than 200 µF"*, so
that constraint is gone.)

| Rail | Capacitors | Nominal | After 50 % derating |
|---|---|---|---|
| `+3V3` | `C4` 4.7 + `C6` 10 + `C12` 1 + `C5` 0.1 + `C18` 47 | 62.8 µF | ~31 µF |
| `VBAT` | `C3` 4.7 + `C20` 100 (+ the cell) | 104.7 µF | ~52 µF |

The 50 % derating figure is the datasheet's own instruction (§7.1.1: *"make sure
ceramic capacitors are derated by 50 %"*). Both rails are comfortably inside the
200 µF ceiling. `VBAT` is also the node any solar / supercap front end would
attach to.

### 5.2 USB-C

`J2` uses the real 16-pad A/B pinout, so **both rows are paralleled**:
`A4`/`B4`/`A9`/`B9` = `VBUS`, `A1`/`B1`/`A12`/`B12` = `GND`, `A6`/`B6` = `D+`,
`A7`/`B7` = `D−`, and the four shield tabs (`S1`) to `GND`. Without that
pairing the cable would only work in one orientation. `CC1` (`A5`) and `CC2`
(`B5`) each get their **own 5.1 kΩ `Rd`** (`R1`/`R2`) to advertise a sink and
must *not* be shorted together. `SBU1`/`SBU2` (`A8`/`B8`) are no-connect.

`D+`/`D−` go through **0 Ω** links (`R3`/`R4`) to the module — the ESP32-C6's USB
PHY already contains its series termination, so the 22 Ω resistors this design
previously carried would have added 44 Ω differential to a 90 Ω pair and
squashed the full-speed eye. The pads are kept as tuning stubs.

`D1` (`USBLC6-2SC6`, SOT-23-6) is an ESD array on `D+`/`D−` and is now
**populated** — 0.95 mm pitch is well within fine-tip hand-soldering. `D7`
(`SMAJ5.0A`, SMA) is a transient clamp on `VBUS`, per MCP73831 datasheet
§6.1.1.2: *"Input overvoltage protection must be used when the input power
source is hot-pluggable. This includes USB cables."*

### 5.3 Battery sense

`R9`/`R10` are **1 MΩ/1 MΩ**, not the 100 kΩ/100 kΩ this design previously used.
The divider sits across the cell permanently, and at 100 kΩ it drew
`4.2 V / 200 kΩ = 21 µA` — three times the ESP32-C6's own 7 µA deep-sleep
current, on a device whose entire premise is deep sleep. At 1 MΩ it draws
2.1 µA.

The trade is a 500 kΩ source impedance, which is far above what the SAR ADC
likes to see directly. `C8` (100 nF) is what makes that work: it is a charge
reservoir some four orders of magnitude larger than the ADC's sampling
capacitor. Allow ~250 ms of settling after wake (the divider's RC is ~50 ms) and
average several samples.

The sense pin is **GPIO0 = ADC1_CH0** (it was GPIO1 on the S3). The C6 has only
one ADC — `ADC1`, seven channels on GPIO0–GPIO6 — so the S3-era rule that `ADC2`
is unusable while Wi-Fi is running simply does not apply here. What replaces it
is a *quantity* problem: those seven pins are also seven of the eight LP GPIOs
the buttons need, which is why the expansion header ends up with exactly one
analog pin. See §7.

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
| `L1` | 47 µH (Sunlord MWSA0402S-470MT / Sumida CDRH2D18-470) | 4×4 mm shielded SMD inductor | boost inductor, VCI→SW |
| `Q1` | Si1304BDL / NX3008NBK N-MOSFET | **SOT-23** | boost switch, gate = `GDR` |
| `R11` | 2.2 Ω 1% | 0805 | `RESE` current-sense resistor |
| `D3`,`D4`,`D5` | MBR0530 Schottky | SOD-123 | boost/charge-pump rectifiers |
| `C9` | 1 µF / **50 V** | 0805 | flying capacitor (ref `C3`) |
| `C10` | 1 µF / **50 V** | 0805 | `VGH` reservoir (ref `C2`) |
| `C11` | 1 µF / **50 V** | 0805 | `VGL` reservoir (ref `C4`) |

The topology, all three diode orientations, `R11` = 2.2 Ω and `L1` = 47 µH were
checked pin-by-pin against the datasheet reference circuit and match it:
`D3` anode=`SW`/cathode=`VGH` (boost rectifier), `D4` anode=`CPMID`/cathode=`GND`
and `D5` anode=`VGL`/cathode=`CPMID` (inverting charge pump for the negative
gate rail), `C9` as the flying cap between `SW` and `CPMID`.

`L1` no longer uses a 1210 chip-inductor land pattern — that was a chip footprint
standing in for a wire-wound part. KiCad has no CDRH2D18 footprint, so this uses
`L_Sunlord_MWSA0402S`, the same class of 4×4 mm shielded power inductor with two
large end pads. **Confirm `Isat` ≥ 500 mA when ordering** — 47 µH sits right at
the edge of that rating for this size class.

Rail decoupling (per datasheet reference, all 1 µF): `C12` VCI/VDDIO(+3V3),
`C13` VDD(core), `C14` VSH1, `C15` VSH2, `C16` VSL, `C17` VCOM.

**Charge-pump caps are 50 V, not the datasheet's 25 V minimum.** `VGH` runs near
+20 V and `VGL` near −20 V; an 0805 25 V X7R at 20 V bias retains only ~20–30 %
of its nominal capacitance, so a nominal 1 µF would behave like ~250 nF exactly
where the charge pump needs it most. 50 V parts in the same 0805 body cost the
same and land nearer 60 % retention.

Display power: **VCI and VDDIO are tied to +3V3** (VDDIO must equal VCI per the
datasheet). **VDD** is the core-logic rail regulated internally from VCI and only
needs a 1 µF cap to VSS. `BS1` (pin 8) is tied to **GND** to select **4-wire
SPI** (datasheet Note 5-5).

**`VPP` goes through a 0 Ω link (`R23`) rather than straight to +3V3.** Worth
knowing: the datasheet's reference circuit on p.24 leaves `VPP` *unconnected* —
only VCI/VDDIO, VDD, VSH1, VSL and VCOM carry capacitors there. Tying `VPP` to
VCI is what most SSD1681-class modules do and is harmless (OTP programming needs
a far higher voltage than 3.3 V), so `R23` is **populated by default**; the link
just means it can be lifted to match the reference exactly if the panel
misbehaves.

Optional external I²C temperature sensor on `TSCL`/`TSDA` (display pins 6/7):
`R12`/`R13` 10 kΩ pull-ups to 3V3 (marked **DNP**) and a 4-pin header `J4`. Leave
unpopulated to use the controller's internal temperature sensor (datasheet says
these pins may be left **Open** when not in use).

---

## 7. Net-by-net connection list & final GPIO assignment

### The C6 pin budget (read this first)

The move from `ESP32-S3-WROOM-1-N8` to `ESP32-C6-WROOM-1-N8` is not a
like-for-like swap of the pin assignment. The S3 module broke out 36 GPIOs; the
C6 module breaks out **23**, and this design uses **all 23**. Worse, three
separate scarce resources on the C6 all live in the *same* eight-pin block:

| Resource | Pins on the C6 | Source |
|---|---|---|
| LP (RTC) GPIO — the only pins EXT1 can wake from | **GPIO0–GPIO7** | `SOC_RTCIO_PIN_COUNT` = 8 |
| `ADC1` (the only ADC — there is no `ADC2`) | **GPIO0–GPIO6** | datasheet Table 3-1 |
| SPI2 IO MUX (`FSPI*`) | GPIO2/4/5/6/7 + GPIO16 | ESP-IDF `spi_pins.h` |

Six buttons plus battery sense claim seven of the eight LP pins. That is what
sets everything else:

- **GPIO7 gets a button**, because it is the one LP pin with no ADC channel
  (Table 3-1 lists no `ADC1_CHn` against `IO7`) — so spending it on a button
  wastes nothing.
- **GPIO0 gets `VBAT_SENSE`** and **GPIO1 is the single pin left over**. GPIO1 is
  `ADC1_CH1` *and* `LP_GPIO1`, so it goes to the expansion header as the only
  pin there that can do analog *or* wake the board.
- **Panel SPI runs through the GPIO matrix**, not the SPI2 IO MUX, because every
  IO MUX pin is a button or UART0. This costs nothing: the matrix runs to 40 MHz
  and an SSD1681 panel is clocked at a few MHz.

**What this costs, stated plainly:** the expansion header goes from 15 GPIOs to
4, the dedicated four-wire SPI block on it is gone, and the two independent ADC
pins collapse into one pin shared with the interrupt line. Nothing else on the
board changes function.

**What it buys:** a RISC-V core, Wi-Fi 6, 802.15.4 (Thread/Zigbee), 7 µA deep
sleep instead of 8 µA, a third of the sustained compute current, and the deletion
of the S3's whole "ADC2 is unusable while Wi-Fi is on" problem.

### ESP32-C6 ↔ e-paper (verified — no collision with USB or strapping pins)

| Display pin | Signal | Net | ESP32-C6 |
|-------------|--------|-----|----------|
| 13 | SCL (SCLK) | `EPD_SCLK` | **GPIO23** |
| 14 | SDA (MOSI) | `EPD_MOSI` | **GPIO22** |
| 12 | CS# | `EPD_CS` | **GPIO21** (`R14` 100 kΩ pull-up) |
| 11 | D/C# | `EPD_DC` | **GPIO20** |
| 10 | RES# | `EPD_RST` | **GPIO19** (`R16` 100 kΩ pull-down) |
| 9 | BUSY | `EPD_BUSY` | **GPIO18** (input) |
| 8 | BS1 | `GND` | tie low → 4-wire SPI |
| 6 / 7 | TSCL / TSDA | `EPD_TSCL` / `EPD_TSDA` | optional I²C temp header (`J4`), else Open |

The panel moved wholesale from `GPIO4–GPIO9` on the S3 to `GPIO18–GPIO23` here.
`GPIO18–23` are the only contiguous block of six pins on the C6 that is neither
LP-domain, ADC-capable, a strapping pin, nor claimed by the USB PHY — which is
exactly why the panel gets them: the panel is the one peripheral on this board
that needs no special pin property at all. Their alternate functions
(`SDIO_CMD/CLK/DATA0-3`, `FSPICS2–5`) are unused here.

### Reserved / special pins

| Signal | ESP32-C6 | Notes |
|--------|----------|-------|
| USB D− | **GPIO12** | via `R4` 0 Ω to USB-C `D−`; fixed by the USB Serial/JTAG PHY |
| USB D+ | **GPIO13** | via `R3` 0 Ω to USB-C `D+`; fixed by the USB Serial/JTAG PHY |
| BOOT strap | **GPIO9** | `R8` 10k pull-up + `SW2` BOOT button |
| Boot-mode strap 2 | **GPIO8** | `R28` 10k pull-up, **populated**; also `J6` pin 7 |
| Battery sense | **GPIO0** (ADC1_CH0) | VBAT ÷2 divider (1M/1M) |
| UART0 TXD/RXD | **GPIO16 / GPIO17** | optional console header `J5` |
| JTAG-source strap | **GPIO15** | `R15` 10 kΩ pull-**up**, **populated**; `STRAP_IO15` |
| SDIO-edge straps | **GPIO4 / GPIO5** | MTMS/MTDI; latched high by the button pull-ups, inert here |

All datasheet references in this section are to
`components/esp32-c6-wroom-1_wroom-1u_datasheet_en.pdf` (v1.4). Strapping-pin
defaults are Table 4-1:
`GPIO9` = weak pull-up (1), and `GPIO8`, `GPIO15`, `MTMS`, `MTDI` all
**floating**.

#### `R15` — GPIO15, and why it is a pull-*up* here

`R15` is **not** optional and must not be depopulated. GPIO15 is the C6's
one strapping pin with no internal pull resistor, and datasheet §4.4 is explicit:
*"This pin does not have any internal pull resistors and the strapping value must
be controlled by the external circuit that cannot be in a high impedance state."*
That is the same sentence the S3 datasheet used about its GPIO3, and it is the
same reason the resistor exists.

**The direction is inverted from the S3 revision, deliberately.** Datasheet Table
4-7: once `EFUSE_JTAG_SEL_ENABLE` is burnt, `GPIO15 = 1` keeps JTAG on the USB
Serial/JTAG controller and `GPIO15 = 0` moves it to the `MTDI`/`MTCK`/`MTMS`/
`MTDO` pads. On the C6 those pads are **GPIO4–GPIO7**, which this board wires to
four of the six buttons — so pad-JTAG is not reachable here at all, and pulling
the strap low would trade a working debug port for an unusable one. With default
(unburnt) eFuses GPIO15 is ignored and USB Serial/JTAG is used regardless; `R15`
is what keeps that true afterwards, and what stops the pin floating meanwhile.

#### `R28` — GPIO8, the one that can brick flashing

`R28` (10 kΩ to `+3V3`, **populated**) is also required. GPIO8 is floating by
default and joint download boot needs `GPIO8 = 1` with `GPIO9 = 0`; datasheet
Table 4-3 notes that `GPIO8 = 0` with `GPIO9 = 0` is an **invalid** combination.
Because GPIO8 is also `J6` pin 7, anything plugged into the expansion header must
not hold it low through reset, or the board stops being flashable over USB. In
normal boot (GPIO9 high) GPIO8 is ignored.

It does *not* disable ROM message printing: Table 4-5 shows UART0 ROM printing is
enabled regardless of GPIO8 while `EFUSE_UART_PRINT_CONTROL` is 0, which is its
default.

#### GPIO4 / GPIO5 (MTMS / MTDI)

These are strapping pins too, for the **SDIO slave** sampling and driving clock
edge (Table 4-4). `R17`/`R18`, the pull-ups on `BTN_UP` and `BTN_DOWN`, latch both
to 1 at reset — unless that button happens to be held down — selecting "rising
edge sampling, rising edge output". This board never uses the SDIO slave
interface, so the setting is inert either way. It is documented so nobody
rediscovers it as a mystery.

### Power / battery nets

| Net | Members |
|-----|---------|
| `VBUS` | USB-C `A4/B4/A9/B9`, MCP73831 VDD, `C1`, ESD `D1`, TVS `D7`, `R6` (STAT LED), `#FLG1` |
| `VBAT` | MCP73831 VBAT, `U3` IN **and** EN, `J3` pin 1 (B+), `C2`, `C3`, `C20`, `R24`, `R9` (sense) |
| `BATT_NEG` | `J3` pin 2 (cell B−), `U4` VSS, `Q2` S1, `C21` — **not** board GND |
| `+3V3` | `U3` OUT, module 3V3, display VCI/VDDIO, `C4/C5/C6/C12/C18`, `R7/R8/R12/R13/R14/R15/R17–R22/R23/R26/R27/R28`, `L1`, header power |
| `GND` | common ground / all decoupling returns / module GND pads / USB-C shield `S1` / `#FLG2` |

`#FLG1`/`#FLG2` are `PWR_FLAG`s (not real parts) marking `VBUS`/`GND` as
externally driven for ERC.

### Expansion header (`J6`, 2×4)

Four spare GPIOs on a 2×4 0.1" header. This was a 2×10 carrying fifteen GPIOs on
the S3 revision; after the panel, the six buttons, USB, UART0 and the two
strapping pins, four is what the C6 has left. Shrinking the connector is the
honest way to say so — a 2×10 with twelve grounds on it would only look like it
kept the capability.

| Pin | Signal | GPIO | Also | Pin | Signal | GPIO | Also |
|----:|--------|------|------|----:|--------|------|------|
| 1 | `+3V3` | — | ≤ 150 mA, see below | 2 | `GND` | — | |
| 3 | `EXP_SDA` | **IO10** | plain digital | 4 | `EXP_SCL` | **IO11** | plain digital |
| 5 | `EXP_ADC_IRQ` | **IO1** | **ADC1_CH1** · LP_GPIO1 (EXT1 wake) | 6 | `GND` | — | |
| 7 | `EXP_IO8` | **IO8** | strapping pin — `R28` pull-up | 8 | `GND` | — | |

**Pin 5 (`IO1`) is the pin that had to be defended.** It is `ADC1_CH1` *and*
`LP_GPIO1`, which makes it simultaneously the board's only spare analog input and
the only header pin that can wake the chip from deep sleep through EXT1. On the
S3 those were two separate jobs spread across three pins (`EXP_ADC_A`,
`EXP_ADC_B`, `EXP_IRQ`); here one pin does all of it, so **a sensor that needs an
interrupt and a sensor that needs an analog input are now mutually exclusive**.
That is a real loss and it is a direct consequence of the part choice, not of the
header layout. It faces a `GND` pin (6) so an analog source still gets a short
return.

**Pins 3/4 (`IO10`/`IO11`) are labelled I²C** because most sensors are I²C. They
are the two remaining pins with no strapping duty and no LP-domain role at all,
which is exactly what makes them the right pair to label. As on the S3 the label
is a convention, not a hardware constraint — the C6 routes I²C through the GPIO
matrix, so any two GPIOs would do. `R26`/`R27` (4.7 kΩ, **DNP**) are the bus
pull-ups: nearly every breakout board already carries its own pair, and two sets
in parallel halve the bus impedance. Fit them if the sensor has none, or if a
long ribbon needs stiffer rising edges. Either way they draw nothing while the
bus idles high, so they cost no sleep current.

**Pin 7 (`IO8`) is the weakest position on the header.** GPIO8 is a strapping pin
that must read 1 at reset for download boot, held there by `R28` — see the `R28`
note above. Anything plugged in here must not drive it low through reset or the
board stops being flashable over USB. It is an ordinary GPIO once the chip is
running.

**There is no SPI block, and there cannot be one.** SPI2's IO MUX pins on the C6
are `GPIO2/4/5/6/7` plus `GPIO16`, every one of which is a button or UART0 here,
and there are not four spare matrix-routable pins left to build a bit-banged or
matrix-routed bus out of either. A SPI peripheral has to share pins 3/4/5/7,
which works (the matrix runs to 40 MHz, far above any sensor) but costs the I²C
and interrupt labels. This is the single biggest capability the board gives up in
moving to the C6.

**Nothing here depends on which module variant was ordered.** The S3 revision
carried footnotes about `IO35–IO37` and `IO47/IO48` being usable only on
non-octal-PSRAM, non-`R16VA` modules. The C6-WROOM-1 series is N4/N8/N16 —
flash only, no PSRAM option at all (datasheet Table 1-1) — so those caveats are
gone entirely.

**Power:** `+3V3` on pin 1 comes straight off `U3`. The regulator is a 1 A part,
but in SOT-23-5 it is not a continuous half-amp supply — see §2 and §10; keep
sustained header draw to ~150 mA. There is no `VBAT` pin on the header on
purpose: the cell is a bare 80C pack behind a low-side protection FET, and
handing an unfused 24 A source to a 0.1" jumper is not a favour.

### User buttons (`SW3`–`SW8`)

D-pad + select + cancel, each wired pin 1 → GPIO, pin 2 → `GND` (active low),
with a **100 kΩ external pull-up to +3V3**. All six sit on **`GPIO2`–`GPIO7`**,
which is six of the C6's eight LP (RTC) IOs — the complete set of pins EXT1 can
wake the chip from.

| Ref | Function | Net | GPIO | Also | Pull-up |
|-----|----------|-----|------|------|---------|
| SW3 | up | `BTN_UP` | **GPIO4** | MTMS · ADC1_CH4 · FSPIHD | `R17` 100k |
| SW4 | down | `BTN_DOWN` | **GPIO5** | MTDI · ADC1_CH5 · FSPIWP | `R18` 100k |
| SW5 | left | `BTN_LEFT` | **GPIO6** | MTCK · ADC1_CH6 · FSPICLK | `R19` 100k |
| SW6 | right | `BTN_RIGHT` | **GPIO7** | MTDO · FSPID — *no ADC* | `R20` 100k |
| SW7 | select | `BTN_SELECT` | **GPIO3** | ADC1_CH3 | `R21` 100k |
| SW8 | cancel | `BTN_CANCEL` | **GPIO2** | ADC1_CH2 · FSPIQ | `R22` 100k |

**On the S3 this allocation was a choice; on the C6 it is arithmetic.** The S3
had RTC capability across `GPIO0–GPIO21`, so the buttons could be moved around
freely to free up whatever else wanted those pins. The C6 has exactly eight LP
IOs (`GPIO0–GPIO7`) and no others can wake the chip, so six buttons take six of
them and the remaining two go to `VBAT_SENSE` (GPIO0) and the header (GPIO1).
There is no arrangement that also leaves an ADC pin or an IO MUX SPI pin free.

Within that constraint two details are still deliberate:

- **`GPIO7` gets a button because it is the only LP pin with no ADC channel**
  (datasheet Table 3-1 lists no `ADC1_CHn` for `IO7`). Spending the board's one
  non-analog LP pin on a button wastes nothing; spending an analog one would.
- **`GPIO0`/`GPIO1` are kept off the buttons** so the analog pair stays intact.
  They carry `XTAL_32K_P`/`XTAL_32K_N` as an alternate function; the module has
  no 32 kHz crystal fitted, so they are ordinary GPIOs here. Fitting one later
  would take both — and with them the battery sense and the header's analog pin.

`GPIO4` and `GPIO5` are `MTMS`/`MTDI`, which are also SDIO-slave clock-edge
strapping pins; `R17`/`R18` latch them high at reset and this board never uses
the SDIO slave interface, so that is inert. See the strapping notes above.

### Why external pull-ups, when the C6 has internal ones

The internal pull-ups live in the digital IO domain and **drop out in deep
sleep**. Keeping them alive across a deep sleep means explicitly enabling the
*LP/RTC* pull-ups (`rtc_gpio_pullup_en()`) on every one of these pins, and if that
is missed — or reset by a later `gpio_config()`, or dropped by an IDF upgrade —
six EXT1 wake sources float. Floating wake sources do not fail loudly; they
produce phantom wakes that quietly drain the battery, which is a miserable bug
to chase on a device that is supposed to sleep for hours at a time.

Six resistors buy a level that is defined by the hardware and cannot be
misconfigured. **100 kΩ, not 10 kΩ**: pressing a button costs 33 µA rather than
330 µA, and 100 kΩ is still enormously stiffer than the leakage it has to
overcome. Firmware may still enable the internal pull-ups in parallel — it is
harmless, and costs nothing while the button is open.

Note the net naming: these are `BTN_*`, never `EXP_IO*`. A net called `EXP_IO3`
that is really the select button is exactly the sort of thing that produces a
layout or firmware mix-up — and on the header side the same rule runs the other
way, where a pin with a job (`EXP_SDA`, `EXP_ADC_IRQ`) is named for the job and
only the genuinely uncommitted spare keeps an `EXP_IOnn` name (`EXP_IO8`).

`SW1` (EN/RESET) and `SW2` (BOOT) use the same FSJM 6 × 6 mm through-hole part
as `SW3`–`SW8` — they are no longer the `B3U-1000P` SMD switch.

---

## 8. Bill of Materials

**PACKAGE / mounting column:** every part is THT, hand-solderable leaded SMD
(SOT-23 / SOT-23-5 / SOT-23-6 / SOD-123 / SMA / 0805 / 1206), a castellated module, or a
breakout adapter. **No exposed-pad (QFN/DFN) parts. No reflow required.**

| Ref | Value / Part number | Package / mounting |
|-----|--------------------|--------------------|
| U1 | ESP32-C6-WROOM-1-N8 (8 MB quad flash) | **Castellated module** (bottom pad optional); footprint `Espressif:ESP32-C6-WROOM-1` |
| U2 | MCP73831T-2ACI/OT (4.2 V) | **SOT-23-5** (hand-solderable SMD) |
| U4 | **DW01A** 1S protection controller | **SOT-23-6** (hand-solderable SMD) |
| Q2 | **FS8205A** dual N-MOSFET, common drain | **SOT-23-6** — *pinout is not the commonly-quoted one, see §4* |
| R24 | 100 Ω (DW01A `VDD` feed) | 0805 |
| R25 | 1 kΩ (DW01A `VM` sense) | 0805 |
| C21 | 100 nF (DW01A `VDD`–`VSS`) | 0805 |
| U3 | **TLV75733PDBVR** (3.3 V, 1 A, `IQ` 25 µA LDO) | **SOT-23-5** (hand-solderable SMD). Pin-compatible with AP2112K-3.3 / XC6220B331MR — see §2 |
| Q1 | Si1304BDL / NX3008NBK N-MOSFET | **SOT-23** |
| D1 | USBLC6-2SC6 ESD array (D+/D−) | **SOT-23-6** (0.95 mm pitch, hand-solderable) |
| D2 | LED (charge status) | **THT** 3 mm LED |
| D3,D4,D5 | MBR0530 Schottky | **SOD-123** (hand-solderable SMD) |
| D7 | SMAJ5.0A (VBUS transient clamp) | **SMA** (hand-solderable SMD) |
| L1 | 47 µH (Sunlord MWSA0402S-470MT / Sumida CDRH2D18-470), **Isat ≥ 500 mA** | 4×4 mm shielded SMD inductor |
| R1,R2 | 5.1 kΩ (USB CC1/CC2 `Rd`) | 0805 |
| R3,R4 | 0 Ω (USB D+/D− links) | 0805 |
| R5 | 10 kΩ (charge-current PROG → 100 mA) | 0805 |
| R6 | 1 kΩ (STAT LED, **returns to VBUS**) | 0805 |
| R7,R8 | 10 kΩ (EN, BOOT pull-ups) | 0805 |
| R9,R10 | 1 MΩ (battery-sense divider) | 0805 |
| R11 | 2.2 Ω 1% (RESE sense) | 0805 |
| R12,R13 | 10 kΩ (I²C temp pull-ups, **DNP**) | 0805 |
| R14 | 100 kΩ (EPD CS pull-up) | 0805 |
| R15 | 10 kΩ (GPIO15 JTAG-source strap pull-**up**, **required**) | 0805 |
| R16 | 100 kΩ (EPD reset pull-down) | 0805 |
| R17–R22 | 100 kΩ (SW3–SW8 button pull-ups) | 0805 |
| R23 | 0 Ω (display VPP link) | 0805 |
| R26,R27 | 4.7 kΩ (`J6` I²C pull-ups, **DNP**) | 0805 |
| R28 | 10 kΩ (GPIO8 boot-mode strap pull-up, **required**) | 0805 |
| C1,C2 | 4.7 µF (charger in/out) | 0805 X7R |
| C3,C4 | 4.7 µF (LDO in/out) | 0805 X7R |
| C18 | 47 µF (+3V3 output bulk) | 1206 X5R |
| C5 | 100 nF (module decoupling) | 0805 |
| C6 | 10 µF (module bulk) | 0805 X7R |
| C7 | 1 µF (EN RC) | 0805 |
| C8 | 100 nF (battery-sense filter) | 0805 |
| C9,C10,C11 | 1 µF / **50 V** (boost flying + VGH/VGL) | 0805 X7R |
| C12 | 1 µF (display VCI/VDDIO) | 0805 |
| C13 | 1 µF (display VDD core) | 0805 |
| C14,C15,C16,C17 | 1 µF / **50 V** (VSH1/VSH2/VSL/VCOM) | 0805 X7R |
| C20 | 100 µF (VBAT / LDO-input burst reservoir) | 1206 X5R |
| J1 | AES200200A00 24-pin 0.5 mm FPC | **FPC-to-0.1" breakout / 0.5 mm ZIF socket** |
| J2 | USB-C receptacle (2.0, sink), 16-pin | `Connector_USB:USB_C_Receptacle_GCT_USB4085` |
| J3 | Turnigy BoltX LiHV 1S 300 mAh 3.8 V 80C (raw cell — protection is on-board, §4) | **JST-PH 2-pin** THT connector |
| J4 | I²C temp sensor *(optional)* | **THT** 1×4 0.1" header |
| J5 | UART console | **THT** 1×4 0.1" header |
| J6 | GPIO expansion (I²C / ADC+IRQ / spare, §7) | **THT** 2×4 0.1" header |
| SW1–SW8 | Tactile push button, FSJM series 6 × 6 mm (EN/RESET, BOOT, D-pad, SELECT, CANCEL) | **THT** 4-pin 6 × 6 mm (Omron/Alps 6.5 × 4.5 mm pitch), `Button_Switch_THT:SW_PUSH_6mm` |

---

## 9. Assembly / soldering notes

- **No reflow, no hot-air, no solder stencil is required.** Every part is
  attachable with a fine-tip soldering iron.
- Solder the **ESP32-C6-WROOM-1-N8** via its edge castellations (drag-solder,
  1.27 mm pitch, 14 pads per side). Its **bottom GND/thermal pad is redundant and
  may be left unsoldered** (GND is on castellations 1 & 28) — no reflow needed.
- Neither regulator needs a heatsink, but both want copper — `U2` more than
  `U3`. See **§10** for the junction-temperature numbers and the layout rules.
- SOT-23 / SOT-23-5 / SOT-23-6 / SOD-123 / SMA / 0805 / 1206 parts hand-solder
  easily; tin one pad, place the part, then solder the remaining pins.
- The finest-pitch SMT part is the ESD array `D1` (SOT-23-6, 0.95 mm pitch),
  which is still comfortable with a fine tip.
- The e-paper FPC connects through an FPC-to-0.1" breakout / 0.5 mm ZIF socket,
  so no fine-pitch FPC soldering is needed on this board.
- **Check PH2.0 polarity with a meter before the first plug-in.** The board has
  no reverse-polarity protection — §4 explains why the old crowbar was removed —
  so a reversed cell will destroy `U4` and possibly `Q2`.
- **`Q2`'s pinout is not the commonly-quoted 8205A one** — see §4 before
  copying connections from another 8205A design. A one-minute DMM check
  confirms it.

## 10. Thermal design (read before layout)

No heatsinks are needed on this board, but two parts want copper. Since there is
no PCB yet, the reasoning is recorded here so it survives to layout time.

### Why copper, not a stick-on heatsink

`U3` is a SOT-23-5 with no thermal pad, and the temptation is to glue a small
heatsink to it. That is the wrong tool, for two reasons the datasheet makes
plain:

**The heat leaves through the leads, not the top.** `RθJC(top)` is
**118.4 °C/W** (§5.4) — that is junction to the *top surface of the plastic*
alone. Any top-mounted heatsink sits in series behind that. So even a
magically perfect heatsink, holding the case at ambient, cannot bring `RθJA`
below ~118 °C/W.

**Copper alone beats that, for free.** TI quotes the same DBV package twice:
**231.1 °C/W** on the JEDEC board (2s2p, and note the qualifier — *"no vias to
internal plane and bottom layer"*) versus **100.8 °C/W** on their EVM. Same die,
same package; the only difference is copper and vias. That is a **2.3×
improvement at zero cost**, and it lands below what a perfect top-side heatsink
could theoretically reach.

A 2.9 × 2.8 mm stick-on sink also means a thermal-tape interface over ~0.08 cm²
and a lump of mass cantilevered off a hand-soldered 5-lead part. More risk of
shearing the part off the board than thermal benefit.

### `U3` junction temperature by load case

`TJ = TA + RθJA × PD` (§7.1.5), `PD = (VIN − VOUT) × IOUT`, worst case at a full
4.2 V cell, `TA` = 25 °C. `TJ(MAX)` = 125 °C, thermal shutdown at 165 °C.

| Load case | `PD` | `TJ` @231 °C/W | `TJ` @100.8 °C/W |
|---|---|---|---|
| Deep sleep | ~0 W | 25 °C | 25 °C |
| Wi-Fi RX, 802.11b/g/n HT20 (78 mA) | 0.070 W | 41 °C | 32 °C |
| **Long processing, 160 MHz single-core (38 mA)** | **0.034 W** | **33 °C** | **28 °C** |
| Wi-Fi TX peak, 802.11b (382 mA, brief) | 0.344 W | 104 °C | 60 °C |
| Continuous 500 mA drawn via `J6` | 0.450 W | **129 °C** ✗ | 70 °C |

Two things fall out of this table:

- **A long compute session is not the thermal case, and the C6 made it even less
  of one.** In modem-sleep at 160 MHz with the CPU running and all peripheral
  clocks enabled the module draws 38 mA (module datasheet Table 6-7) — a
  *low-current* sustained load, and roughly a third of what the S3's 240 MHz
  dual-core figure was. 0.034 W is 33 °C of junction temperature even on a
  deliberately bad board. It is a non-event.
- **The only case that breaches `TJ(MAX)` is a sustained half-amp pulled through
  the expansion header**, and copper alone takes it from 129 °C to 70 °C. That
  is the case the §2 warning is about, and it is fixed by layout rather than by
  a heatsink.

### `U2` is the part that actually runs hot

The charger, not the regulator, is the sustained dissipator. Out of
preconditioning at 100 mA with a 5.5 V input, `PD = (5.5 − 2.8) × 0.1 = 0.27 W`
— nearly 3× `U3`'s compute-session figure, and it holds for the *entire charge
cycle* rather than for seconds. At the MCP73831's 230 °C/W minimum-copper `θJA`
that is `TJ` ≈ 87 °C; with the large copper area the datasheet mentions
(130 °C/W) it is ≈ 60 °C. **If copper is poured in only one place, pour it at
`U2`.**

### Layout rules

1. `U2` first: flood copper around its `VSS` pin (pin 2) and give it a via field
   to the opposite-side plane. MCP73831 datasheet §6.2 and Figures 6-4/6-5 show
   the intended pattern.
2. `U3`: pin 2 (`GND`) is the primary heat path. Connect it to the ground pour
   with a **solid** connection, not a thermal-relief spoke, and drop 4–8 × 0.3 mm
   vias into the pour right beside the pin. Widen the `IN`/`OUT` copper too —
   those leads conduct heat as well. TLV757P §7.4.1: *"use copper planes for
   device connections"*, *"place thermal vias around the device"*.
3. Keep `CIN`/`COUT` (`C3`/`C4`) tight to the pins on both regulators.
4. Keep both away from the module's antenna keep-out and from the panel boost
   switching node (`EPD_SW`).
5. If a future revision really does need a continuous half-amp on `+3V3`, change
   the package rather than adding a heatsink: the **DYD** variant is the same
   SOT-23-5 pinout with an exposed pad at 92.5 °C/W — at the cost of needing
   reflow, which is why it is not the default here.

---

## 11. Status / not included

- **PCB layout is not included yet** — this is a schematic-level deliverable,
  but every real (BOM) component has a KiCad standard-library footprint
  assigned, so *Update PCB from Schematic* runs without "no footprint assigned"
  errors. Chip passives are **0805** (1206 for the two bulk caps) to stay
  hand-solderable, the MBR0530 Schottkys use `D_SOD-123`, `D6`/`D7` use `D_SMA`
  and `L1` uses `L_Sunlord_MWSA0402S`; `gen_sch.py` fails loudly if a BOM
  component is left without a footprint.
- **`J2` (USB-C) now maps 1:1 to the footprint.** The symbol's pin *numbers* are
  the real pad names (`A1 A4 A5 A6 A7 A8 A9 A12 / B1 B4 B5 B6 B7 B8 B9 B12` plus
  the four shield tabs, all numbered `S1`), matching
  `Connector_USB:USB_C_Receptacle_GCT_USB4085` exactly — verified against the
  KiCad 8.0.9 footprint file rather than assumed. Both rows are paralleled, so
  the cable works either way up. `D1` (USBLC6-2SC6) likewise uses the real
  SOT-23-6 pinout (1/6=I/O1, 3/4=I/O2, 2=GND, 5=VBUS).
- **`U4`/`Q2` add on-board 1S battery protection** (§4), so `J3` takes a raw
  cell. `Q2`'s pinout is **not** the commonly-quoted 8205A mapping — it comes
  from the Tech Public package drawing, and copying pin assignments from another
  8205A design would be wrong.
- **There is no reverse-polarity protection** — the old `D6` crowbar was removed
  because it would have been a 1 A diode standing in front of a 24 A cell with
  nothing to interrupt the fault (§4). Check cell polarity with a meter.
- **The main processor is now the `ESP32-C6-WROOM-1-N8` (RISC-V), replacing the
  `ESP32-S3-WROOM-1-N8` (Xtensa).** Same 18.0 × 25.5 × 3.1 mm outline, completely
  different pads (29 pins vs 41) and a completely different pin map. **Any
  firmware written against the S3 revision has a stale pin map — every GPIO
  number on this board changed** — and the target must be rebuilt for
  `esp32c6`. `U1` also needs Espressif's KiCad library installed; see the top of
  this file.
- **`J6` shrank from a 2×10 to a 2×4** (I²C pair, one ADC+wake pin, one spare —
  §7). The C6 has 23 usable GPIOs against the S3's 36 and this design uses all
  23, so four is what is left after the panel, buttons, USB, UART0 and the
  strapping pins. The header's four-wire SPI block and its second ADC input are
  gone; `R28` is a new required part (GPIO8 boot strap).
- Component placement in the schematic is auto-generated and rough; connectivity
  is by global label.
- **ERC has not been re-run since these changes** — `kicad-cli` was not available
  in the environment they were made in. The generator's own self-checks pass (see
  below) and the S-expression parses with balanced structure, but run the ERC
  command below before committing to a layout.

## Regenerating

```
cd hardware
python3 gen_sch.py            # regenerates .kicad_sch, epaper.kicad_sym, sym-lib-table
kicad-cli sch erc epaper-display.kicad_sch          # -> expect 0 violations
kicad-cli sch export netlist epaper-display.kicad_sch
```

`gen_sch.py` self-checks the netlist on every run and exits non-zero on:

- a BOM component with no footprint,
- a duplicate reference designator,
- a net key naming a pin that does not exist on that symbol,
- a net with only one member, or one that goes open once DNP parts are
  depopulated (this is what catches a half-applied net rename — the failure mode
  that ERC *cannot* see, because a dangling global label is perfectly legal),
- a net with more than one driving output.
