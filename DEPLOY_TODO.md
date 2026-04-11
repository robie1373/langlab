# LangLab homeLab Deploy — Todo

## Key decisions (already researched)
- VMID: 111 (next after omada/110)
- IP: 192.168.20.11/24 (next free static on VLAN 20 below .100)
- Node: pve
- VLAN: 20 (lab infrastructure)
- Resources: 1 CPU, 1 GB RAM, 16 GB disk
- Tailscale hostname: langlab.vimba-stairs.ts.net
- Internal port: 8080 → nginx → HTTPS 443
- State dir: /var/lib/langlab/ (db + audio files)
- Python deps: stdlib + local fsrs.py only (no pip!)
- Source: pkgs.fetchFromGitHub robie1373/langlab (public repo)
- Secrets: single langlab-env.age file containing KEY=value pairs:
    GEMINI_API_KEY=...
    CLAUDE_API_KEY=...

## Step 1 — langlab repo
- [ ] Add LANGLAB_DATA_DIR env var support to server.py
      (currently hardcodes BASE_DIR / 'data'; NixOS needs /var/lib/langlab)
- [ ] Commit + push

## Step 2 — homeLab repo (docs/state first — required by CLAUDE.md)
- [ ] Create docs/design-docs/langlab.md
- [ ] Add stub entry to services.yaml (VMID 111, IP 192.168.20.11, status: planned)
- [ ] Add 192.168.20.11 to docs/network/vlans.md static IP table
- [ ] Commit

## Step 3 — nixos-config repo
- [ ] Read modules/hosts (or modules/hosts.nix) to understand flake-parts
      nixosConfigurations pattern — need this before writing host config
- [ ] Create modules/_system/langlab.nix  (service + nginx + tailscale-cert + agenix)
- [ ] Create hosts/langlab/configuration.nix
- [ ] Create hosts/langlab/hardware-configuration.nix  (stub — nixos-anywhere overwrites)
- [ ] Create hosts/langlab/disko.nix  (copy ntfy pattern, bump disk to 16GB)
- [ ] Create hosts/langlab/ssh_host_ed25519_key.pub  (placeholder — replaced at provision time)
- [ ] Update secrets/secrets.nix — add langlab host key + langlab-env.age entry
- [ ] Re-key tailscale-auth-key.age to include langlab:
      nix run github:ryantm/agenix -- -r
- [ ] Encrypt langlab-env.age:
      op read op://devops/LangLab\ env/notesPlain | age -r "<langlab-pubkey>" -o secrets/langlab-env.age
      (create the 1Password item first with GEMINI_API_KEY= and CLAUDE_API_KEY=)
- [ ] Wire langlab into flake nixosConfigurations (follow existing pattern)
- [ ] Commit

## Step 4 — VM provisioning (manual, on pve)
Per new-nixos-service.md runbook:
- [ ] Clone template 9001 → VMID 111, name=langlab
- [ ] Set NIC VLAN tag 20
- [ ] Bump RAM to 2048 MB (kexec requirement)
- [ ] Fix efidisk: delete cloned efidisk0, recreate fresh, set boot order=virtio0
- [ ] Start VM; manual EFI boot step in PVE console (Boot Manager → EFI boot from file)
- [ ] Get DHCP IP from VLAN 20 lease (via OPNsense or pve2 jump)
- [ ] Generate host SSH key, store private key in 1Password, commit public key
- [ ] Encrypt all langlab secrets with the real host public key
- [ ] nixos-anywhere (flipper must be on VLAN 20 port or lab SSID)
- [ ] Switch back to OVMF after nixos-anywhere, restart
      (Tailscale joins automatically on first boot via tailscale-autoconnect.nix)

## Step 5 — Post-deploy verification
- [ ] SSH via Tailscale: ssh root@langlab.vimba-stairs.ts.net
- [ ] systemctl status langlab
- [ ] curl https://langlab.vimba-stairs.ts.net/api/users
- [ ] wc -c /run/agenix/langlab-env  (must be > 0)
- [ ] Reset RAM: qm set 111 --memory 1024

## Step 6 — Closeout
- [ ] Update docs/homeLab-state-map.md (add to compute resources table)
- [ ] Update services.yaml stub → full conforming entry
- [ ] Import Korean vocab: python3 scripts/import_apkg.py <deck.apkg>
- [ ] Ingest VTT+MP3 data for player view
- [ ] Update homeLab BEARING.md
