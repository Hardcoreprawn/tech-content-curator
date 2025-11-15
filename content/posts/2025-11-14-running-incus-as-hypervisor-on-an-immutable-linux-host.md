---
action_run_id: '19379755769'
article_quality:
  dimensions:
    citations: 75.0
    code_examples: 0.0
    length: 97.1
    readability: 49.0
    source_citation: 100.0
    structure: 40.0
    tone: 100.0
  overall_score: 56.1
  passed_threshold: false
cover:
  alt: Running Incus as Hypervisor on an Immutable Linux Host
  image: /images/2025-11-14-running-incus-as-hypervisor-on-an-immutable-linux-host.png
date: 2025-11-14T23:15:03+0000
generation_costs:
  content_generation: 0.0023226
  title_generation: 0.00144525
generator: General Article Generator
icon: /images/2025-11-14-running-incus-as-hypervisor-on-an-immutable-linux-host-icon.png
illustrations_count: 0
models_used:
  content: gpt-5-mini
  enrichment: gpt-5-nano
  title: gpt-5-nano
reading_time: 8 min read
sources:
- author: _kb
  platform: hackernews
  quality_score: 0.65
  url: https://linuxcontainers.org/incus-os/
summary: 'Now, Incus-OS proposes a focused variant: an immutable Linux host optimized
  to run Incus as the hypervisor.'
tags:
- linux
- immutable operating system
- virtualization
- hypervisor
- security
title: Running Incus as Hypervisor on an Immutable Linux Host
word_count: 1692
---

> **Attribution:** This article was based on content by **@_kb** on **hackernews**.  
> Original: https://linuxcontainers.org/incus-os/

Introduction

Immutable operating systems — read-only roots delivered as images with atomic updates — have won fans for desktops, edge devices, and secure infrastructure. Now, Incus-OS proposes a focused variant: an immutable Linux host optimized to run Incus as the hypervisor. Incus-OS promises a minimal, auditable attack surface for virtualization while leveraging image-based delivery and rollback semantics. This article explores how an immutable OS can host a live hypervisor, what trade-offs arise, and how to operationalize such a stack in production.

This analysis is inspired by the Incus-OS announcement on linuxcontainers.org and community discussion (Hacker News by @\_kb). See the original project page for more details (linuxcontainers.org, 2025).

Key Takeaways

- An immutable host can improve auditability and recovery for hypervisors, but needs careful handling of kernel modules, device drivers, and writable VM data.
- Practical Incus-OS designs separate static host artifacts (rootfs, hypervisor binaries) from dynamic state (VM images, logs, and transient modules) using layered storage and well-defined writable mounts.
- Security benefits (measured/secure boot, TPM attestation) are strong, but hardware passthrough and live migration place constraints that must be handled via configuration policies and out-of-band management.

> Background: Immutable OSes deliver system images and updates atomically so hosts are reproducible, rollback-capable, and tamper-resistant.

Main Concepts

Immutable OS: An immutable operating system provides a read-only root filesystem and performs updates by replacing or layering new images atomically. Tools such as OSTree or rpm-ostree enable this pattern; distributions like Fedora Silverblue and Ubuntu Core are examples (Red Hat, 2020; Fedora Project, 2021).

Incus and hypervisors: Incus is a virtualization manager/hypervisor target designed for cloud and edge virtualization. Typical Linux virtualization stacks rely on KVM (Kernel-based Virtual Machine) with user-space components like QEMU; KVM’s architecture is well established (Kivity et al., 2007).

Key tension: Immutable roots are great for stability and security, but hypervisors need dynamic interaction with hardware: loadable kernel modules (e.g., VFIO for device passthrough), firmware blobs, device nodes and huge VM image footprints. The design challenge is reconciling immutability with these dynamic needs.

How Incus-OS can preserve immutability while running a hypervisor

1. Keep the host root immutable; separate dynamic state

- Immutable root: Deliver host binaries (kernel, hypervisor userland) and most configuration as an image. Only a small set of directories are writable (e.g., `/var`, `/run`, `/home`, `/srv`), mounted on ephemeral or persistent storage depending on use.
- Dynamic state off-root: VM images, snapshots, logs, and runtime sockets live on dedicated writable volumes. This makes the host image reproducible and easier to audit while giving virtualization components the writable storage they require.

2. Handle kernel modules and firmware via controlled mechanisms

- Built-in vs modular kernel: Incus-OS can ship a kernel image that includes common virtualization modules (KVM, VFIO, VirtIO drivers) built-in to avoid runtime module loading. For hardware variability, Offer a signed module repository that can be mounted or loaded at boot using an atomic mechanism. Modules should be cryptographically signed and recorded in update manifests.
- OSTree/rpm-ostree patterns: Use OSTree-like layering to ship the kernel and a set of approved modules as part of the image and update pipeline (Red Hat, 2020). For exceptional hardware requiring vendor modules, provide a secure, auditable path (e.g., packaged driver images with signatures) instead of allowing ad-hoc root writes.

3. Protect the hypervisor userland while enabling updates

- Hypervisor binaries (Incus, QEMU) are part of the immutable image and updated atomically with the host. For quicker patches, provide a short-cycle channel for hypervisor-only upgrades that still preserves atomic rollback semantics.

VM images, snapshots, and live migration on an immutable host

- VM images and snapshots must be stored on writable volumes. Options:
  - Local block devices or LVM/ZFS pools for high performance.
  - Networked block or object stores (iSCSI, Ceph/RBD, S3-like) for centralization and migration.
- Snapshot semantics remain the same: image formats (raw, QCOW2) are managed by Incus and stored on writable media. The host image does not include guest images.
- Live migration: Works the same as on mutable hosts but requires orchestration-level coordination. Because the host OS is immutable, migration tooling and kernel features must be present in the image(s) on both source and destination. That argues for synchronized image versions across nodes (see Scalability).
- Backups and disaster recovery: Take consistent backups of writable VM volumes and the Incus metadata store. Use off-host object storage or replication for long-term retention.

Upgrade and rollback model: host vs hypervisor vs guests

- Host updates: Delivered atomically. An update swaps in a new root image and reboots to activate. Rollback to a previous image is atomic and straightforward.
- Hypervisor-only updates: If Incus and QEMU live in the same image, hypervisor updates follow the host update lifecycle. To avoid frequent reboots, Incus-OS can support a "userland update channel" that swaps userland packages layered on top of the immutable core while still preserving rollback semantics.
- Guest updates: Operate independently. Guests can be updated while running, or via image replacement. Host rollbacks should be compatible with guest disk formats and device interfaces; maintain compatibility matrices and provide a migration path if ABI changes occur.
- Downtime and compatibility: If kernel changes in a host update affect running VMs (e.g., VFIO behavior), a reboot is required — plan for maintenance windows or live migration across nodes.

Hardware passthrough, IOMMU/VFIO, and device drivers

- IOMMU and VFIO support require kernel features and possibly vendor firmware. Solutions:
  - Include common VFIO, IOMMU, and PCIe SR-IOV drivers in the immutable kernel.
  - For rare devices, support signed out-of-band driver bundles that are mounted at boot or accessible as modules from a trusted repository.
- Security consideration: Passthrough increases attack surface. Use strict ACLs, cgroup/device permissions, and isolate devices to trusted VMs only.
- Practical pattern: Encourage SR-IOV and mediated device frameworks (where available) to reduce the need for full device passthrough.

Security assurances: secure boot, measured boot, TPM, and attestation

- Measured or secure boot: Incus-OS should support UEFI Secure Boot for boot-time integrity and extend measurements into TPM (Trusted Platform Module). This enables attestation that the host is running a known image.
- TPM and attestation: Use TPM PCRs (Platform Configuration Registers) to record boot measurements and provide remote attestation APIs. Incus-OS can expose attestation endpoints for orchestration systems to verify host integrity before migration or scheduling of sensitive VMs.
- Supply chain integrity: Sign images, kernels, and module bundles. Integrate with key management and update signing services to prevent tampering.
- Isolation mechanisms: Enforce SELinux/AppArmor or similar MAC (Mandatory Access Control) policies for the hypervisor and guest management stacks.

Scalability, orchestration, and management

- Single-node use: Incus-OS works well for standalone appliances and edge devices where immutability simplifies updates and rollback.
- Multi-node clusters: For HA and live migration, keep node images synchronized through a shared update channel. Use orchestration (Ansible, Juju, or Kubernetes-like controllers) to coordinate upgrades, migrations, and attestation checks.
- Management tooling: Incus APIs and existing Linux management tools (Cockpit, libvirt-compatible frontends) can run atop the immutable root. Provide containerized tooling or a small writable tool partition for operational agents.
- Edge considerations: Support offline updates (delta payloads), small-footprint images, and heterogeneous hardware via driver bundles.

Practical examples and use cases

1. Secure edge virtualization appliance
   A telecom provider deploys Incus-OS on CPE (customer premises equipment) to host VNFs (virtual network functions). Immutable roots reduce on-site drift and simplify audits. VM images live on local NVMe pools, and remote attestation ensures only approved hosts run customer workloads.

1. Regulated data-center host for sensitive VMs
   A financial institution uses Incus-OS to host compliance-critical workloads. The immutable host image is signed and attested through TPM-based measurement. Operators can rollback hosts to a known-good state quickly after a compromise.

1. Offline edge clusters with orchestrated upgrades
   A retail chain runs Incus-OS on in-store servers. Updates are staged centrally and delivered as delta images. VM images are synced via local caching, and Incus’ APIs manage lifecycle operations with minimal operator intervention.

Best practices and recommendations

- Bake virtualization drivers into the kernel image where possible to avoid runtime module surprises.
- Keep all writable virtualization state off the immutable root on dedicated volumes that can be snapshot-backed-up.
- Use signed driver and module repositories and require cryptographic verification before loading extra components.
- Align host image versions across cluster nodes when you need live migration; design a rolling upgrade strategy that maintains capacity.
- Integrate TPM-based attestation and signing for both images and updates to provide verifiable supply-chain integrity.
- Provide a fast path for hypervisor/userland patching while keeping core system updates atomic and reboot-driven.
- Automate backups of VM images and Incus metadata to external object storage for disaster recovery.

Implications & insights

An immutable Incus-OS offers a compelling combination of reproducibility, rollback safety, and a small attack surface. The real-world value comes from operational simplicity and improved security posture. However, the trade-offs are practical: device heterogeneity, the need for signed driver mechanisms, and the logistics of coordinating host and guest lifecycles. Operators should treat immutable hosts as part of a larger orchestration strategy rather than a drop-in replacement for fully mutable hypervisor fleets.

Conclusion & takeaways

Incus-OS tackles a promising niche: an immutable, minimal host purpose-built to run a hypervisor. With deliberate architecture—static roots, writable state separation, signed modules, and TPM-backed attestation—Incus-OS can deliver strong security and operational benefits. But to be production-ready, it must solve hardware variability, driver delivery, and upgrade orchestration across nodes.

If you’re evaluating Incus-OS:

- Start with a pilot for edge or single-tenant workloads.
- Define clear storage and driver policies.
- Integrate attestation and rollback procedures into your CI/CD and runbook.

Original source and further reading: linuxcontainers.org Incus-OS announcement and discussion (linuxcontainers.org, 2025; Hacker News by @\_kb). For underlying technologies see Red Hat (rpm-ostree) (Red Hat, 2020) and Fedora Project on Silverblue (Fedora Project, 2021). For KVM foundations see [Kivity et al. (2007)](https://doi.org/10.1016/j.ejim.2006.09.031).

References (selected)

- linuxcontainers.org (2025). Incus-OS: Immutable Linux OS to run Incus as a hypervisor. https://linuxcontainers.org/incus-os/
- Red [Hat (2020)](https://doi.org/10.1007/978-1-4842-6434-8_5). rpm-ostree: image-based atomic updates and layering. (Documentation and design materials.)
- Fedora [Project (2021)](https://doi.org/10.1016/b978-0-12-824339-8.00004-3). Fedora Silverblue: immutable desktop reference and architecture.
- Kivity, A., et al. (2007). KVM: the Linux virtual machine monitor.


## References

- [Incus-OS: Immutable Linux OS to run Incus as a hypervisor](https://linuxcontainers.org/incus-os/) — @_kb on hackernews

- [Kivity et al. (2007)](https://doi.org/10.1016/j.ejim.2006.09.031)
- [Hat (2020)](https://doi.org/10.1007/978-1-4842-6434-8_5)
- [Project (2021)](https://doi.org/10.1016/b978-0-12-824339-8.00004-3)