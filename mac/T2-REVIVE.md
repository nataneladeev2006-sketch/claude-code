# Handoff: revive the T2 chip of a MacBook Pro 15" 2018 from a Windows laptop

You are Claude Code running on the user's Windows laptop, ideally in an
**Administrator PowerShell** (WSL2 Ubuntu is also installed). A cloud Claude
session helped until now but can't reach this laptop, so this file is what it
learned. Work through it **with the user**, one small step at a time.

## About the user

- Not experienced with Macs or Linux. Writes casual English; Hebrew is their
  first language (explaining in Hebrew is fine).
- Pasting into the Ubuntu terminal is hard for them, so **run commands
  yourself** instead of asking them to type.
- They are at the Mac for the key presses. Say exactly which keys and port to
  use, and what they should see.

## The problem

- Target: MacBook Pro 15-inch 2018, model A1990 (EMC 3215), Apple T2 chip:
  `iBridge2,3`, board `j680ap`, CPID `0x8012`, BDID `0x0b`.
- The internal SSD was erased from Recovery Assistant, so there is no macOS
  and no local Recovery.
- Internet Recovery (Option+Command+R and Command+R) always fails with
  **-2100F** or **-2003F**. Already tried: iPhone hotspot (Maximize
  Compatibility on, phone renamed "iPhone", 4G instead of 5G) and another
  Wi-Fi network.
- No second Mac is available, so Apple Configurator is out.
- Plan: **revive** the T2 firmware (bridgeOS) in DFU with **restorekit**
  (https://github.com/fcjr/restorekit), then retry Internet Recovery.
- A USB installer won't help: T2 Secure Boot blocks external boot by default,
  and that setting can only be changed from Recovery.

## Put the Mac into DFU (this has worked once)

1. Connect a USB-C **data** cable from the Windows laptop to the Mac's **left
   side, FRONT port** (closest to the trackpad). That's the DFU port on this
   model. Put the Mac's charger in a **right-side** port and plug in nothing
   else.
2. Turn the Mac fully off: hold Touch ID (top right, end of the Touch Bar)
   ~10 s, wait ~10 s, touch nothing.
3. Enter DFU:
   1. Press and hold Touch ID.
   2. While holding it, add **right Shift + left Option + left Control**.
   3. Hold all four ~3 s.
   4. Let go of the three keys but **keep holding Touch ID** until DFU shows
      up on Windows (up to ~10 s).
   - If that misses, try B: Touch ID 1 s, then all four 8 s, then release all.
   - Or try C: tap Touch ID once, then immediately hold all four ~3 s.
   - The user reached DFU after trying these three; they didn't say which one
     worked.
   - Don't hold the three keys 7+ s *before* pressing power: that's an SMC
     reset, not DFU.
4. Watch Device Manager, or poll `restorekit list` for ~60 s, to see which
   mode it's in:

| What Windows shows | Meaning |
| --- | --- |
| `05ac:1227`, "Apple Mobile Device (DFU Mode)" | **DFU, correct.** The Mac screen stays black. |
| `05ac:8600`, "Apple T2 Controller" (Device Manager: "Apple USB Multiplexor" + "NCM Data") | T2 booted normally. Right port, missed timing. |
| `05ac:1680` billboard device | Only the Mac's USB-C controller. Seen before the cable moved to the front-left port. |
| Globe or Apple logo on the Mac screen | It booted normally. Turn it off and retry. |

## What already happened on Windows

Everything ran in an **elevated** PowerShell. Without elevation, the Scoop
shim fails with "Could not create process".

- Installed via Scoop:
  `scoop bucket add fcjr https://github.com/fcjr/scoop-fcjr` then
  `scoop install restorekit-cli` (0.6.0).
- `restorekit setup-driver` printed
  `bound WinUSB to Apple device (mode 0x1227)`.
- `restorekit list` printed:
  ```
  MacBook Pro (15-inch, 2018/2019) [dfu mode]
    usb: 05ac:1227 (class 0x00 per-interface, rev 0.00)
    identifier: iBridge2,3
    chip: CPID:8012  board: BDID:0b
    iBoot: iBoot-3401.0.0.1.16
  ```
- Firmware: `restorekit --cache-dir C:\rk download` saved
  `C:\rk\iBridge2,1,...,iBridge2,8_11.0_24P6005_Restore.ipsw`
  (742,648,126 bytes, bridgeOS 11.0, build 24P6005). In WSL this is
  `/mnt/c/rk/`.
- **Always pass `--cache-dir C:\rk`.** Without it, revive failed with
  `ipsw_open ...\AppData\Roaming\restorekit\firmwares\...: No such file or directory`
  and `no ipsw file given`.
- **The blocker:** `restorekit --cache-dir C:\rk -v revive` failed twice the
  same way:
  ```
  Found device in DFU mode
  Identified device as j680ap, iBridge2,3
  ...
  Variant: Customer Upgrade Install (IPSW)
  This restore will update the device without erasing user data.
  Checking IPSW for required components...
  All required components found in IPSW
  Getting ApNonce in DFU mode...
  Trying to fetch new SHSH blob
  Getting SepNonce in dfu mode...
  Unable to add img4 tags to TSS request
  Unable to get SHSH blobs for this device
  error: restore failed (exit -1)
  ```
  No nonce hex was printed after "Getting ApNonce in DFU mode...". In
  idevicerestore, where these messages come from, that happens when the
  device info has no nonce, so the TSS request lacks ApNonce/SepNonce. A
  likely cause is that the DFU nonce string (USB string descriptor 1,
  `NONC:` / `SNON:`) isn't being read on Windows. That is a guess: confirm it
  before relying on it.

## Next steps (suggested order)

1. **Quick checks on Windows.**
   - Check for a newer restorekit: `scoop update restorekit-cli`.
   - Look for a debug or trace option in `restorekit --help` and
     `restorekit revive --help`.
   - Try reading string descriptor 1 of `05ac:1227` directly to test the
     guess above.
   - The maintainer fixes Windows reports quickly (issue #41 was fixed in
     0.6.0). Offer to help the user file an issue with the `-v` log.
2. **Run the Linux build inside WSL2, with usbipd-win passing the Mac through.**
   1. Install usbipd-win: `winget install --exact dorssel.usbipd-win`.
   2. Install restorekit's Linux CLI in Ubuntu.
      - `sudo snap install restorekit-cli` failed with "error: unable to
        contact snap store". This is unresolved; check WSL internet, DNS and
        snapd.
      - The README says the release binaries are statically linked, so a
        GitHub release tarball avoids snap.
      - Run it as root, or install the udev rule from the README.
      - From Windows, you get root in WSL without the user's password:
        `wsl -d Ubuntu -u root -- <command>`.
   3. With the Mac in DFU, attach it to WSL:
      1. `usbipd list` and note the BUSID of `05ac:1227`.
      2. `usbipd bind --busid <BUSID>` (needs admin; add `--force` if needed).
      3. `usbipd attach --wsl --busid <BUSID> --auto-attach` (keep it running).
      4. In WSL, `lsusb` should list `05ac:1227`.
   4. **Watch out for reconnects.**
      - During revive/restore the Mac disconnects and returns with other Apple
        USB IDs (DFU `1227`, recovery `1281`, restore mode). Each one must
        reach WSL, or the process stalls.
      - usbipd-win 4.2+ has auto-bind policies (`usbipd policy --help`) and
        auto-attach. Set them up before starting.
   5. Run `sudo restorekit list`, then
      `sudo restorekit --cache-dir /mnt/c/rk -v revive`. If reading from
      `/mnt/c` is slow, copy the IPSW to the Linux disk first.
3. **If WSL can't keep the device through the reconnects,** boot the laptop
   from an **Ubuntu live USB** (Rufus, 8 GB+ stick) and run the Linux CLI
   there.
   - You won't be running in that live session, so write the steps down for
     the user first.
   - The Windows drive may be BitLocker-encrypted, so plan to re-download the
     IPSW in the live session rather than read `C:\rk`.
4. **If revive succeeds but Internet Recovery still fails,** use `restore`
   instead of `revive`. `restore` **erases** the T2 and the SSD (the SSD is
   already empty). Ask the user first.
5. **Last resort:** borrow any Mac on macOS 14+ for 30 minutes and use Apple
   Configurator, Apple's official method.

## After the firmware is fixed

- Power on holding **Option+Command+R** until the globe appears.
- Join Wi-Fi or the iPhone hotspot, then choose Reinstall macOS. The download
  is about 13–15 GB.
- If Activation Lock asks for a previous owner's Apple ID, only that owner
  can remove it. Don't try to bypass it.

## Rules

- A failed **revive** is safe to retry, because DFU lives in the T2's boot ROM.
- Ask before anything destructive: `restore`, writing a USB stick, or changing
  boot settings on the Windows laptop. In Rufus, double-check the target disk.
- Show the user real output. Never invent results.
