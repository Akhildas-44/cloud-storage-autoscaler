# Bidirectional Automated Cloud Storage Controller with Asynchronous DR Wrapper Pipeline

A production-grade, state-aware cloud storage orchestration platform designed to eliminate enterprise block-storage underutilization and prevent high-velocity application outages.

While AWS natively supports dynamic volume expansion via the Elastic Block Store (EBS) control plane, downscaling remains fundamentally restricted due to block-corruption and filesystem shrinkage constraints. This platform implements a stateless, safe block-migration pipeline that  offers automated bidirectional scaling under active database workloads.

##  Architecture Design & System Boundaries

```text
[Start Pipeline] ──► 1. DR Guard (Backup Tracking Tags)
                            │
                            ▼
                     2. Launch Daemon (Asynchronous Popen Stream)
                            │
                            ▼
                     3. Telemetry Check (Continuous Low/High Metric Polling)
                        ├── Usage > 80% ──► Native AWS Up-scaling (modify_volume)
                        └── Usage < 20% ──► Invoke Cloud Optimizer (Down-scaling Surgery)
                                                    │
                                                    ▼
                                             4. Form gp3 Target & Sync Data
```
##  Low-Level Technical Mechanics

* **Asynchronous Telemetry Tracking (`daemon.py`)**: Implements an isolated, continuous-loop background agent that samples block utilization via native non-blocking SSH execution layers. Processes data patterns over a line-buffered FIFO queue window (`collections.deque`) via a Sliding Window Moving Average algorithm to damp out transient metric spikes and filter transient read anomalies.
* **Emergency Upside Scaling**: If utilization crosses the 80% threshold pressure zone, the daemon bypasses filesystem manipulation, triggering direct cloud control-plane modifications (`modify_volume`) to immediately expand disk capacity and double resource layouts on the fly, proactively mitigating production out-of-memory outages.
* **Atomic Zero-Downtime Downscaling (`cloud_optimizer.py`)**: Provisions a lean gp3 target volume, maps it case-insensitively using hardware identifiers directly via the NVMe controller (`/dev/disk/by-id/`), and handles initial background replication. During the final sync pass, it locks application I/O lanes for a fraction of a second using `fsfreeze` to guarantee data consistency, swaps block mount targets instantly, and executes an online kernel buffer flush (`blockdev --flushbufs`) before permanently decommissioning the legacy drive asset.
* **DR & Metadata Compliance Guard (`pipeline.py`)**: Intercepts regional cost-allocation and administrative tags *before* the shrink pass occurs, handles the background process lifecycle asynchronously via an unbuffered text stream scraper, and dynamically re-stretches original enterprise tracking metadata onto the fresh target disk block layout by cross-referencing live virtual attachment matrices.
