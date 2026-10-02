# Simulator trade study

Research background for choosing the Satellite Sim; current product scope and implementation requirements are in the [documentation index](../specs/project-plan.md#build-specifications).

Every claim below is checked against the project's own GitHub repository, licence file, or official documentation; the URL is inline. Verified 1 Oct 2026.

## Question

The original pitch said we would build around an existing simulator. We are instead writing a small Python Satellite Sim inside our FastAPI server. Is that the right call for the [three MVP Challenges](../specs/project-plan.md#first-software-demo) and a team of one lead plus four beginners at about 5 hours a week?

Two terms first. A **ground system** (also "mission control software") is the software operators use on Earth to send commands and display telemetry. **C2** means "command and control", the same job. A **spacecraft simulator** pretends to be the satellite. Two of the four options below are ground systems, not simulators.

## Comparison

| | NASA NOS3 | OpenC3 COSMOS | Yamcs | Custom Python Satellite Sim |
| --- | --- | --- | --- | --- |
| What it is | Simulator suite: flight software, "dynamics and environment simulations, and software-based models of spacecraft hardware", plus a ground station ([README](https://github.com/nasa/nos3)). Flight software is [NASA cFS](https://github.com/nasa/cFS) by default, F' optional ([docs](https://github.com/nasa/nos3/blob/main/docs/wiki/NOS3_Flight_Software.md)). It bundles a ground system rather than being one: YAMCS, COSMOS 4/5, F' or AIT ([docs](https://github.com/nasa/nos3/blob/main/docs/wiki/NOS3_Ground_Software.md)). | Ground system: "Command, Control and Communication" software to "send commands to and receive data from one or more embedded systems" ([repo](https://github.com/OpenC3/cosmos)). Ships a demo plugin (`openc3-cosmos-demo`), not a spacecraft model. | Ground system: "a mission control framework developed in Java" ([README](https://github.com/yamcs/yamcs)). Its example includes "a simple simulator of a landing spacecraft"; the [quickstart](https://yamcs.org/getting-started) uses a separate `simulator.py`. | A satellite model written by us, implementing [packet format v1](../specs/packet-format-v1.md) and the scripted pass. |
| Licence | NOSA 1.3 ([README](https://github.com/nasa/nos3#license)); contributors must send NASA a contributor form. | **Changed in COSMOS 7 (Mar 2026)** from AGPL to the [OpenC3 Builder's License](https://github.com/OpenC3/cosmos/blob/main/LICENSE.md), based on Elastic License 2.0. It says: "You may not provide the software or its functionality to third parties as any part of a hosted or managed service" ([licence](https://github.com/OpenC3/cosmos/blob/main/LICENSE.md); transition announced in the [v7.0.0 notes](https://github.com/OpenC3/cosmos/releases/tag/v7.0.0)). | AGPLv3; commercial licence available ([README](https://github.com/yamcs/yamcs#license)). | Ours. |
| Footprint and deployment | Vagrant/VirtualBox VM or Linux with Docker Compose ([getting started](https://nos3.readthedocs.io/en/latest/NOS3_Getting_Started.html)). Default VM: 4 CPUs, 8192 MB ([Vagrantfile](https://github.com/nasa/nos3/blob/main/Vagrantfile)); docs say more "should probably be added if possible". Container count not documented. | Docker Compose. Minimum "8GB RAM, 1 CPU, 80GB Disk"; recommended 16 GB, 2+ CPUs ([installation](https://docs.openc3.com/docs/getting-started/installation)). [`compose.yaml`](https://github.com/OpenC3/cosmos/blob/main/compose.yaml) defines 9 services (Redis ×2, time-series DB, buckets, APIs, operator, Traefik, init). | Java 17+ and Maven ([getting started](https://yamcs.org/getting-started)); one server process plus a simulator. RAM not documented. | Part of our one FastAPI process; no extra services. |
| Languages a contributor touches | Mostly C, plus Shell, Python, CMake ([GitHub languages](https://github.com/nasa/nos3)). | Ruby, Python, Vue/JavaScript ([repo](https://github.com/OpenC3/cosmos)); targets defined in COSMOS text config files. | Java, TypeScript; packets defined in XTCE XML ([getting started](https://yamcs.org/getting-started)). | Python only. |
| Fit with our packet format and Challenges | Uses cFS's own commands; KnightSat's format would need a new NOS3 component in C. Rich orbit/attitude realism we do not need for MVP. | Could describe our packets (CCSDS fields via `TELEMETRY`/`APPEND_ITEM`, [docs](https://docs.openc3.com/docs/configuration/telemetry)) and check our CRC with its configurable [CRC protocol](https://docs.openc3.com/docs/configuration/protocols). Still needs a satellite to talk to. | Can describe our packets in XTCE. Still needs a satellite to talk to. | Built for exactly the three Challenges and our byte layout. |
| Embed in one-process FastAPI + our browser UI | No: separate VM or container stack with its own GUIs. | No: separate stack with its own web UI. Hosting it for learners may conflict with the licence limitation above. | No: separate JVM with its own web UI (port 8090). | Yes. |
| Beginner learning curve | Steep: cFS, C, CMake, 42, Docker. | Steep: container stack plus Ruby/Python config. | Steep: Java, Maven, XTCE. | Lowest; still requires learning packet bytes and CRC. |
| Activity | Active: v1_07_05 (30 Jun 2026), pushed 29 Sep 2026. | Active: v7.4.1 (24 Sep 2026). | Active: 5.13.6 (1 Oct 2026). | Depends on us. |

## Recommendation

Build the custom Python Satellite Sim for the MVP. The deciding facts are documented, not guessed. COSMOS's stated minimum (8 GB RAM, 80 GB disk) and NOS3's 8 GB default VM would each take more than our single small server without adding anything the three Challenges need. None of the three can live inside our one FastAPI process or our browser UI. Each would ask beginners to learn C, Ruby or Java before writing their first packet. COSMOS and Yamcs are not simulators at all, so choosing one would still leave us writing the satellite.

The pitch wording was wrong, not the decision. The report should say plainly that we changed course and why.

What we lose: real flight software (cFS) and real orbit and attitude physics (NOS3); tested, professional operator tools such as packet viewers, scripting and limit alarms (COSMOS, Yamcs); built-in standards support such as XTCE, COP-1 and CFDP ([NOS3 ground docs](https://github.com/nasa/nos3/blob/main/docs/wiki/NOS3_Ground_Software.md)); and the credibility of saying we use established mission software. Our simulator is a teaching model, and its bugs are ours.

What we would reuse later:

- **Yamcs as a "real ground software" lesson.** A learner points Yamcs at KnightSat using an XTCE file for our format. Its AGPL licence permits hosting if we publish any changes we make.
- **COSMOS for the same lesson, only after a licence check.** The Builder's License bars offering it "as any part of a hosted or managed service"; whether a hosted university course counts needs a decision from the university before we host it.
- **NOS3 as a second-semester stretch.** For example, a demo or optional lab showing cFS and 42 next to KnightSat, run on a separate machine with at least the 8 GB VM.
