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
- Source: flake input github:robie1373/langlab (flake = false; pinned in flake.lock)
- Secrets: single langlab-env.age file containing KEY=value pairs:
    GEMINI_API_KEY=...
    CLAUDE_API_KEY=...

## Step 1 — langlab repo ✓ DONE
- [x] Add LANGLAB_DATA_DIR env var support to server.py
- [x] Commit + push (commit 1bf252c)

## Step 2 — homeLab repo ✓ DONE
- [x] Create docs/design-docs/langlab.md
- [x] Create docs/services/langlab.md (provisioning checklist + ops notes)
- [x] Add stub entry to services.yaml
- [x] Add 192.168.20.11 to docs/network/vlans.md

## Step 3 — nixos-config repo ✓ DONE (except langlab-env.age)
- [x] Create modules/_system/langlab.nix
- [x] Create modules/hosts/langlab/default.nix
- [x] Create hosts/langlab/configuration.nix
- [x] Create hosts/langlab/hardware-configuration.nix (stub)
- [x] Create hosts/langlab/disko.nix
- [x] Generate real host SSH key → stored in 1Password devops/"langlab host SSH key"
- [x] hosts/langlab/ssh_host_ed25519_key.pub — real key committed
- [x] secrets/secrets.nix — langlab key wired in
- [x] tailscale-auth-key.age rekeyed to include langlab
- [x] Wire langlab into flake nixosConfigurations
- [ ] **NEXT: Create "LangLab env" 1Password item** (devops vault):
      GEMINI_API_KEY=<from Google AI Studio>
      CLAUDE_API_KEY=<from Anthropic console>
      Store as Secure Note with notesPlain field.
- [ ] **NEXT: Encrypt langlab-env.age:**
      ```
      eval $(op signin)
      cd ~/nixos-config/secrets
      op read 'op://devops/LangLab env/notesPlain' | \
        nix run nixpkgs#age -- \
          -r "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDb0aYMGmaB70EJZ32jqi9+tKncViDYp9CEYUAuoa2Td" \
          -o langlab-env.age
      git add langlab-env.age && git commit -m "Add langlab-env.age"
      ```

## Step 4 — VM provisioning (partially done)
- [x] Clone template 9001 → VMID 111, name=langlab
- [x] Set NIC VLAN tag 20
- [x] Bump RAM to 2048 MB
- [x] Fix efidisk: deleted cloned efidisk0, recreated fresh, boot order=virtio0
- [ ] **NEXT: Connect flipper to VLAN 20** (lab AP or wired port)
- [ ] **NEXT: Start VM and get DHCP IP:**
      ```
      ssh root@192.168.7.40 "qm start 111"
      # SeaBIOS boot — no manual EFI step needed (start under SeaBIOS, switch to OVMF after)
      # Get IP: watch OPNsense DHCP leases or check from pve after agent comes up
      ```
- [ ] **NEXT: Run nixos-anywhere** (from flipper on VLAN 20):
      ```
      eval $(op signin)
      mkdir -p /tmp/langlab-bootstrap/etc/ssh
      op read "op://devops/langlab host SSH key/notesPlain" \
        > /tmp/langlab-bootstrap/etc/ssh/ssh_host_ed25519_key
      chmod 600 /tmp/langlab-bootstrap/etc/ssh/ssh_host_ed25519_key
      nixos-anywhere \
        --flake ~/nixos-config#langlab \
        --extra-files /tmp/langlab-bootstrap \
        root@<DHCP-IP>
      shred -u /tmp/langlab-bootstrap/etc/ssh/ssh_host_ed25519_key
      rm -rf /tmp/langlab-bootstrap
      ```
- [ ] After nixos-anywhere — switch to OVMF and restart:
      ```
      ssh root@192.168.7.40 "qm stop 111 --skiplock"
      ssh root@192.168.7.40 "qm set 111 --bios ovmf"
      ssh root@192.168.7.40 "qm start 111"
      ```
      (Tailscale joins automatically via tailscale-autoconnect.nix)

## Step 5 — Post-deploy verification
- [ ] SSH via Tailscale: ssh root@langlab.vimba-stairs.ts.net
- [ ] systemctl status langlab
- [ ] curl https://langlab.vimba-stairs.ts.net/api/users
- [ ] wc -c /run/agenix/langlab-env  (must be > 0)
- [ ] Reset RAM: ssh root@192.168.7.40 "qm set 111 --memory 1024"

## Step 6 — Closeout
- [ ] Update docs/homeLab-state-map.md (add to compute resources table)
- [ ] Update services.yaml stub → full conforming entry
- [ ] Import Korean vocab: python3 scripts/import_apkg.py <deck.apkg>
- [ ] Ingest VTT+MP3 data for player view
- [ ] Update homeLab BEARING.md
