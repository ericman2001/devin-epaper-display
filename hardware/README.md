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
| `epaper-display-schematic.pdf` | Rendered schematic (**stale**, see note below) |
| `gen_sch.py` | Generator that produces the schematic/library from the netlist definition |

Connectivity is expressed with **global labels**, so the netlist is correct even
though the auto-generated component placement is rough. Re-open in KiCad and
rearrange/route as desired.

> ⚠️ **`epaper-display-schematic.pdf` is stale** — it predates the current
> revision and has not been re-rendered, because `kicad-cli` was not available
> where these changes were made. Regenerate it (and re-run ERC) with the
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
                  +--> 0R  --> D-/D+ (GPIO19 / GPIO20, native USB-Serial/JTAG)
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
              ESP32-S3-WROOM-1-N8 (3V3)                        AES200200A00 e-paper (VCI/VDDIO)
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
- **Programming/serial:** ESP32-S3 native USB-Serial/JTAG on **GPIO19 (D-)** and
  **GPIO20 (D+)**. No external USB-UART bridge required. UART0 (GPIO43/44) is
  also broken out on a header for an optional console.

---

## 2. Regulator choice — TLV75733P (linear, low-IQ)

The ESP32-S3's Wi-Fi TX current peaks at **355 mA** (802.11b @20.5 dBm, module
datasheet Table 6-4), and the module datasheet lists `IVDD ≥ 0.5 A` as a
*recommended operating condition* (Table 6-2). The regulator therefore has to
cover a ~0.5 A burst on a rail that is otherwise drawing microamps.

Two earlier revisions got this wrong in opposite directions: an `MCP1700-3302E/TO`
(250 mA) that browned out during transmit, then an **`MCP1825S-3302`** (500 mA,
SOT-223) that handled the burst but drew **120 µA typ / 220 µA max of quiescent
current** — roughly 15× the ESP32-S3's own deep-sleep draw, which made the
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

Estimated life on a 500 mAh cell (1850 mWh), including ~1.8 mWh/day of active
energy and ~1.2 mWh/day of cell self-discharge at 2 %/month:

| Regulator | `IQ` | Total standby | Est. life |
|---|---|---|---|
| MCP1825S (old) | 120 µA | ~135 µA | ~4 months |
| **TLV75733P** | **25 µA** | **~40 µA** | **~9 months** |
| TPS7A0533 (200 mA) | 1 µA | ~16 µA | ~14 months |

Dropping 120 → 25 µA roughly doubles the achievable life. Chasing 25 → 1 µA
gains less than it looks: the cell's own self-discharge and the panel's 1–5 µA
sleep current start to dominate, and the only SOT-23-5 parts down there
(TPS7A05) top out at **200 mA**, which cannot serve a 355 mA TX burst. 25 µA is
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
| E-paper CS | `R14` **100k** pull-up to 3V3 on **GPIO6** | keeps the panel deselected during reset/power-up |
| E-paper reset | `R16` **100k** pull-down to GND on **GPIO8** | holds active-low `RES#` asserted while the ESP32 is in reset; the panel stays in reset until firmware drives GPIO8 high, alongside the `EN`/`SW1` reset RC |
| GPIO45 / GPIO46 | left at datasheet default | strapping pins — see §7 |
| GPIO3 | `R15` 10k pull-down (**populated**) | required, not optional — see §7 |

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
thermal regulation even on modest copper. A 100 mA charge is ~0.2 C for a
500 mAh cell — a full charge takes longer, but this is a device that sits on a
desk and sleeps, and the charger no longer runs hot.

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

### Battery protection — read this before plugging a cell in

There is **no over-discharge protection on this board**. The MCP73831 has none,
and the LDO will happily pull a cell down past 2.5 V and ruin it. `J3` therefore
**requires a LiPo pack with an integrated protection PCM** — this is a hard BOM
requirement, not a preference, and it is called out on the schematic sheet.

`D6` (SS14, SMA) is a reverse-polarity **crowbar** across the battery input:
cathode to `VBAT`, anode to `GND`. Normally reverse-biased and invisible. If a
cell is plugged in backwards it forward-biases, clamps the reversed input at
about −0.4 V instead of letting it reach −4.2 V, and shorts the cell — which the
pack's PCM then interrupts. So the crowbar and the protected-cell requirement
are one mechanism, not two: **`D6` does nothing useful with an unprotected
cell.** JST-PH polarity is not standardised between cell vendors (Adafruit and
SparkFun are wired opposite), so check yours with a meter before first plug-in.

`D6` costs a little reverse leakage (a few µA at 3.7 V for an SS14). If you are
chasing the last microamps, substitute a low-`Ir` Schottky such as a PMEG
device — but fix the LDO `Iq` first, it is 30× larger.

---

## 5. Power path (net summary)

```
USB-C VBUS ──► MCP73831 VDD (C1 4.7µF, D7 SMAJ5.0A TVS)
MCP73831 VBAT ──► VBAT node ──► JST-PH LiPo (C2 4.7µF, D6 reverse clamp)
VBAT ──► TLV75733P IN/EN (C3 4.7µF + C20 100µF) ──► +3V3 (C4 4.7µF + C18 47µF) ──► ESP32-S3 + e-paper
VBAT ──► R9/R10 (1M/1M divider, C8 100nF) ──► GPIO1 (ADC1_CH0) battery sense
```

### 5.1 Rail buffering

The module datasheet lists `IVDD ≥ 0.5 A` as a *recommended operating
condition* (Table 6-2), and an 802.11b TX burst is **355 mA peak** (Table 6-4).
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

`D+`/`D−` go through **0 Ω** links (`R3`/`R4`) to the module — the ESP32-S3's USB
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
`4.2 V / 200 kΩ = 21 µA` — roughly triple the ESP32-S3's own deep-sleep current,
on a device whose entire premise is deep sleep. At 1 MΩ it draws 2.1 µA.

The trade is a 500 kΩ source impedance, which is far above what the SAR ADC
likes to see directly. `C8` (100 nF) is what makes that work: it is a charge
reservoir some four orders of magnitude larger than the ADC's sampling
capacitor. Allow ~250 ms of settling after wake (the divider's RC is ~50 ms) and
average several samples. `ADC1` is used deliberately — `ADC2` is unavailable
while Wi-Fi is active.

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

### ESP32-S3 ↔ e-paper (verified — no collision with USB or strapping pins)

| Display pin | Signal | Net | ESP32-S3 |
|-------------|--------|-----|----------|
| 13 | SCL (SCLK) | `EPD_SCLK` | **GPIO4** |
| 14 | SDA (MOSI) | `EPD_MOSI` | **GPIO5** |
| 12 | CS# | `EPD_CS` | **GPIO6** (`R14` 100 kΩ pull-up) |
| 11 | D/C# | `EPD_DC` | **GPIO7** |
| 10 | RES# | `EPD_RST` | **GPIO8** (`R16` 100 kΩ pull-down) |
| 9 | BUSY | `EPD_BUSY` | **GPIO9** (input) |
| 8 | BS1 | `GND` | tie low → 4-wire SPI |
| 6 / 7 | TSCL / TSDA | `EPD_TSCL` / `EPD_TSDA` | optional I²C temp header (`J4`), else Open |

`GPIO4–7` are the prompt-specified SPI pins; `RES`/`BUSY` use the next free
`GPIO8`/`GPIO9`. None collide with USB (GPIO19/20) or the strapping pins
(GPIO0/45/46/3).

### Reserved / special pins

| Signal | ESP32-S3 | Notes |
|--------|----------|-------|
| USB D- | **GPIO19** | via `R4` 0 Ω to USB-C `D-` |
| USB D+ | **GPIO20** | via `R3` 0 Ω to USB-C `D+` |
| BOOT strap | **GPIO0** | 10k pull-up + BOOT button |
| Battery sense | **GPIO1** (ADC1_CH0) | VBAT ÷2 divider (1M/1M) |
| UART0 TXD/RXD | **GPIO43 / GPIO44** | optional console header `J5` |
| VDD_SPI strap | **GPIO45** | left at default (weak pull-down = 0); NC |
| ROM-msg / boot strap | **GPIO46** | left at default (weak pull-down = 0); NC |
| JTAG-source strap | **GPIO3** | `R15` 10 kΩ pull-down, **populated**; `STRAP_IO3` |

Strapping-pin defaults are from the ESP32-S3-WROOM-1 datasheet Table 4-1
(GPIO0 = weak pull-up 1, GPIO3 = floating, GPIO45/46 = weak pull-down 0).

`R15` is **not** optional and must not be depopulated. GPIO3 is the one strapping
pin with no internal pull resistor, and datasheet §4.4 is explicit: *"This pin
does not have any internal pull resistors and the strapping value must be
controlled by the external circuit that cannot be in a high impedance state."*
With default (unburnt) eFuses the strap value happens to be ignored, so a
floating GPIO3 boots fine today — it breaks the moment anyone burns
`EFUSE_STRAP_JTAG_SEL`, and until then it is simply a floating CMOS input.

### Power / battery nets

| Net | Members |
|-----|---------|
| `VBUS` | USB-C `A4/B4/A9/B9`, MCP73831 VDD, `C1`, ESD `D1`, TVS `D7`, `R6` (STAT LED), `#FLG1` |
| `VBAT` | MCP73831 VBAT, `U3` IN **and** EN, JST `J3`, `C2`, `C3`, `C20`, `D6` (reverse clamp), `R9` (sense) |
| `+3V3` | `U3` OUT, module 3V3, display VCI/VDDIO, `C4/C5/C6/C12/C18`, `R7/R8/R12/R13/R14/R17–R22/R23`, `L1`, header power |
| `GND` | common ground / all decoupling returns / module GND pads / USB-C shield `S1` / `#FLG2` |

`#FLG1`/`#FLG2` are `PWR_FLAG`s (not real parts) marking `VBUS`/`GND` as
externally driven for ERC.

### Spare GPIO expansion header (`J6`, 2×12)

Exposes 3V3, GND and spare GPIOs `IO15–IO18, IO21, IO35–IO42, IO47, IO48` for
future peripherals. `IO2` and `IO10–IO14` are **no longer** on this header —
they are dedicated to the user buttons `SW3`–`SW8` (below), so the six freed
header pins are tied to `GND` as extra ground returns (the connector stays a
2×12).

### User buttons (`SW3`–`SW8`)

D-pad + select + cancel, each wired pin 1 → GPIO, pin 2 → `GND` (active low),
with a **100 kΩ external pull-up to +3V3**. All six are **RTC-capable GPIOs
(GPIO0–21)**, so any of them can be used as a deep-sleep wake source.

| Ref | Function | Net | GPIO | Pull-up |
|-----|----------|-----|------|---------|
| SW3 | up | `BTN_UP` | **GPIO2** | `R17` 100k |
| SW4 | down | `BTN_DOWN` | **GPIO10** | `R18` 100k |
| SW5 | left | `BTN_LEFT` | **GPIO11** | `R19` 100k |
| SW6 | right | `BTN_RIGHT` | **GPIO12** | `R20` 100k |
| SW7 | select | `BTN_SELECT` | **GPIO13** | `R21` 100k |
| SW8 | cancel | `BTN_CANCEL` | **GPIO14** | `R22` 100k |

### Why external pull-ups, when the S3 has internal ones

The internal pull-ups live in the digital IO domain and **drop out in deep
sleep**. Keeping them alive across a deep sleep means explicitly enabling the
*RTC* pull-ups (`rtc_gpio_pullup_en()`) on every one of these pins, and if that
is missed — or reset by a later `gpio_config()`, or dropped by an IDF upgrade —
six EXT1 wake sources float. Floating wake sources do not fail loudly; they
produce phantom wakes that quietly drain the battery, which is a miserable bug
to chase on a device that is supposed to sleep for hours at a time.

Six resistors buy a level that is defined by the hardware and cannot be
misconfigured. **100 kΩ, not 10 kΩ**: pressing a button costs 33 µA rather than
330 µA, and 100 kΩ is still enormously stiffer than the leakage it has to
overcome. Firmware may still enable the internal pull-ups in parallel — it is
harmless, and costs nothing while the button is open.

Note the net rename: these are now `BTN_*` rather than `EXP_IO*`. The old names
were left over from when these pins were on the expansion header, and a net
called `EXP_IO13` that is really the select button is exactly the sort of thing
that produces a layout or firmware mix-up.

`SW1` (EN/RESET) and `SW2` (BOOT) use the same FSJM 6 × 6 mm through-hole part
as `SW3`–`SW8` — they are no longer the `B3U-1000P` SMD switch.

---

## 8. Bill of Materials

**PACKAGE / mounting column:** every part is THT, hand-solderable leaded SMD
(SOT-23 / SOT-23-5 / SOT-23-6 / SOD-123 / SMA / 0805 / 1206), a castellated module, or a
breakout adapter. **No exposed-pad (QFN/DFN) parts. No reflow required.**

| Ref | Value / Part number | Package / mounting |
|-----|--------------------|--------------------|
| U1 | ESP32-S3-WROOM-1-N8 (quad flash, no PSRAM) | **Castellated module** (bottom pad optional) |
| U2 | MCP73831T-2ACI/OT (4.2 V) | **SOT-23-5** (hand-solderable SMD) |
| U3 | **TLV75733PDBVR** (3.3 V, 1 A, `IQ` 25 µA LDO) | **SOT-23-5** (hand-solderable SMD). Pin-compatible with AP2112K-3.3 / XC6220B331MR — see §2 |
| Q1 | Si1304BDL / NX3008NBK N-MOSFET | **SOT-23** |
| D1 | USBLC6-2SC6 ESD array (D+/D−) | **SOT-23-6** (0.95 mm pitch, hand-solderable) |
| D2 | LED (charge status) | **THT** 3 mm LED |
| D3,D4,D5 | MBR0530 Schottky | **SOD-123** (hand-solderable SMD) |
| D6 | SS14 (battery reverse-polarity clamp) | **SMA** (hand-solderable SMD) |
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
| R15 | 10 kΩ (GPIO3 strap pull-down, **required**) | 0805 |
| R16 | 100 kΩ (EPD reset pull-down) | 0805 |
| R17–R22 | 100 kΩ (SW3–SW8 button pull-ups) | 0805 |
| R23 | 0 Ω (display VPP link) | 0805 |
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
| J3 | LiPo battery — **must have an integrated protection PCM** | **JST-PH 2-pin** THT connector |
| J4 | I²C temp sensor *(optional)* | **THT** 1×4 0.1" header |
| J5 | UART console | **THT** 1×4 0.1" header |
| J6 | GPIO expansion | **THT** 2×12 0.1" header |
| SW1–SW8 | Tactile push button, FSJM series 6 × 6 mm (EN/RESET, BOOT, D-pad, SELECT, CANCEL) | **THT** 4-pin 6 × 6 mm (Omron/Alps 6.5 × 4.5 mm pitch), `Button_Switch_THT:SW_PUSH_6mm` |

---

## 9. Assembly / soldering notes

- **No reflow, no hot-air, no solder stencil is required.** Every part is
  attachable with a fine-tip soldering iron.
- Solder the **ESP32-S3-WROOM-1-N8** via its edge castellations (drag-solder). Its
  **bottom GND/thermal pad is redundant and may be left unsoldered** (GND is on
  castellations 1 & 40) — no reflow needed.
- Neither regulator needs a heatsink, but both want copper — `U2` more than
  `U3`. See **§10** for the junction-temperature numbers and the layout rules.
- SOT-23 / SOT-23-5 / SOT-23-6 / SOD-123 / SMA / 0805 / 1206 parts hand-solder
  easily; tin one pad, place the part, then solder the remaining pins.
- The finest-pitch SMT part is the ESD array `D1` (SOT-23-6, 0.95 mm pitch),
  which is still comfortable with a fine tip.
- The e-paper FPC connects through an FPC-to-0.1" breakout / 0.5 mm ZIF socket,
  so no fine-pitch FPC soldering is needed on this board.
- **Check LiPo polarity with a meter before the first plug-in.** JST-PH wiring is
  not standardised between cell vendors. `D6` will crowbar a reversed cell rather
  than let it destroy `U2`/`U3`, but that only works with a protected pack.

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
| Wi-Fi RX / connected (95 mA) | 0.086 W | 45 °C | 34 °C |
| **Long processing, 240 MHz dual-core (108 mA)** | **0.097 W** | **47 °C** | **35 °C** |
| Wi-Fi TX peak, 802.11b (355 mA, brief) | 0.320 W | 99 °C | 57 °C |
| Continuous 500 mA drawn via `J6` | 0.450 W | **129 °C** ✗ | 70 °C |

Two things fall out of this table:

- **A long compute session is not the thermal case.** At 240 MHz with both cores
  running 128-bit accesses the module draws ~108 mA (module datasheet Table 6-6,
  modem-sleep) — a *low-current* sustained load. 0.097 W is 47 °C of junction
  temperature even on a deliberately bad board. It is a non-event.
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
- **`U3`'s 120 µA quiescent current is the open item.** See §2 — everything else
  on the board is sized for microamps and the regulator now dominates standby by
  more than an order of magnitude.
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
