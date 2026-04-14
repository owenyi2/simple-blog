---
date: 2026-04-14
title: NixOS
---
# Installation

The installation is fairly standard, feel free to skip. This part not a guide. This part is about how I almost bricked my laptop. 

Resources: 
- Official Installation Manual https://nixos.org/manual/nixos/stable/index.html#ch-installation
- Another installation guide?: https://nixos.wiki/wiki/NixOS_Installation_Guide
	- I followed this one
- NixOS download: https://nixos.org/download/

My old Lenovo laptop had Windows and Ubuntu dual-booted. My goal was to also boot NixOS on this laptop. The plan was to shrink the Ubuntu partition and use the free space to install NixOS. 

## Burning the ISO onto a USB

I downloaded the NixOS minimal installation `.iso` file. Run [`lsblk`](https://www.man7.org/linux/man-pages/man8/lsblk.8.html) to get something like 

```
NAME MAJ:MIN RM SIZE RO TYPE MOUNTPOINT  
sda 8:0 0 465.8G 0 disk  
├─sda1 8:1 0 500M 0 part /boot  
├─sda2 8:2 0 50.0G 0 part /  
└─sda3 8:3 0 415.3G 0 part /home  
sdb 8:16 1 16G 0 disk  
└─sdb1 8:17 1 16G 0 part /media/usb
```

My USB device is identified as `sdb` so I would run the [`dd`](https://www.man7.org/linux/man-pages/man8/lsblk.8.html) command to burn the image onto the USB. This step took like 30 minutes. Also it is normal if at the end it stalls. 

```
dd if=path/to/nixos.iso of=/dev/sdb bs=4M status=progress conv=fdatasync
```

## Partitioning 

### Initial faffing about

I first tried shrinking the Ubuntu partition from inside Ubuntu using `gparted`. Turns out you can't resize the partition that you are currently booting from. (Which sounds obvious in retrospect). So instead, I booted from the USB and ran [`parted`](https://www.man7.org/linux/man-pages/man8/parted.8.html). I am greeted by a interactive prompt like so

```
[nixos@nixos:~]$ sudo parted
GNU Parted 3.5
Using /dev/sda
Welcome to GNU Parted! Type 'help' to view a list of commands.
(parted) 
```
Running the `print` command after the prompt gave me something like this

```
(parted) print
Model: ATA TOSHIBA 
Disk /dev/sda: 500GB
Sector size (logical/physical): 512B/4096B
Partition Table: msdos
Disk Flags:

Number  Start   End     Size    Type     File system  Flags
 1      1049kB  524MB   523MB   primary  ntfs 
 2      524MB   266GB   266GB   primary  ntfs 
 3      266GB   267GB   537MB   primary  fat32        boot, esp
 4      267GB   500GB   133GB   extended
 5      267GB   500GB   133GB   logical
(parted)
```

- Partition 2 is my Windows partition. "ntfs" is a Windows file system. Partition 1 is probably some auxiliary windows partition maybe a boot partition or something 
- Partition 5 contained my Ubuntu partition 

At first I tried to run `resizepart 4 100GB` which gave an error. Turns out the 3rd argument should be the new End rather than the desired size. After resizing it to the correct end, I tried to run [`resize2fs`](https://www.man7.org/linux/man-pages/man8/resize2fs.8.html) and I encountered a loop like in this post https://unix.stackexchange.com/questions/593908/how-to-recover-filesystem-and-physical-size-mismatch.

Running `resize2fs` gave the error

```
resize2fs: Can't read a block bitmap while trying to resize /dev/sda3
Please run 'e2fsck -fy /dev/sda3' to fix the filesystem
after the aborted resize operation.
```

and running [`e2fsck`](https://www.man7.org/linux/man-pages/man8/e2fsck.8.html), gave the error

```
The filesystem size (according to the superblock) is 186122240 blocks
The physical size of the device is 159907584 blocks
Either the superblock or the partition table is likely to be corrupt!
Abort<y>? 
```

Essentially the filesystem resides within a partition. In order to safely shrink a partition, one must shrink the filesystem inside the partition before shrinking the partition. Otherwise one will have portion of the filesystem outside the partition which 1) the filesystem no longer has access to and 2) could be overwritten by processes out of the filesystems control.

One more interesting thing, while trying to undo my mistake by expanding the partition back to the original 500GB end, I tried to resize partition 5 first. Since partition 5 is a logical partition contained inside the physical partition 4, I had to first resize partition 4 and then resize partition 5.

### What I was supposed to do

So basically after I expanded the partition back to 500GB, I ran the following correct sequence

```
sudo e2fsck -f /dev/sda5
sudo resize2fs /dev/sda5 133G 
sudo parted /dev/sda  
(parted) resizepart 5 400GB
(parted) quit
sudo e2fsck -f /dev/sda5
sudo parted /dev/sda  
(parted) mkpart logical ext4 400GB 500GB
(parted) quit
sudo e2fsck -f /dev/sda6
```

## Mounting

This part went fairly smoothly. I run the [`mount`](https://www.man7.org/linux/man-pages/man8/mount.8.html) command to attach the `/mnt` folder in the USB to the newly created partition `/dev/sda6`. 

```
sudo mount /dev/sda6 /mnt
sudo mkdir -p /mnt/boot
```

I followed this commands to create a swapfile

```
sudo dd if=/dev/zero of=/mnt/.swapfile bs=1024 count=2097152 # 2GB size
sudo chmod 600 /mnt/.swapfile
sudo mkswap /mnt/.swapfile
sudo swapon /mnt/.swapfile
```

## Creating a NixOS configuration

Our first NixOS command is to create a config. `sudo nixos-generate-config --root /mnt`. This creates a default `configuration.nix` file inside `/mnt/etc/nixos/configuration.nix`.

A large part of time configuring NixOS will be spend modifying `.nix` files from within the `/etc/nixos/` folder. 

Run `sudo -e /mnt/etc/nixos/configuration.nix` to edit the file. Nano was the default editor that came up. I installed Vim shortly after.

Some things to configure
- Adding a user
- Configuring boot loader

I had a couple small issues with configuring the bootloader. Initially I left `boot.loader.grub.efiSupport = true` and `boot.loader.grub.device = "nodev"`. NixOS didn't boot. To check if I had EFI support I booted Ubuntu and ran `ls /sys/firmware/efi`. Since that folder was not found, it meant my computer didn't have EFI. Disabling the option fixed it. The next issue I had was on the NixOS boot screen I couldn't find the option to boot Ubuntu or Windows. The fix was to enable `boot.loader.grub.useOSProber = true`. This allows the boot loader to look for other operating systems to boot.

"configuration.nix":

```
  # Add a user!
  users.users.owenyi = {
    isNormalUser = true;
    extraGroups = [ "wheel" ]; # Sudo access
    home = "/home/owenyi";
  };
  
  # Use th eGRUB 2 boot loader.
  boot.loader.grub.enable = true;
  boot.loader.grub.efiSupport = false;
  boot.loader.grub.useOSProber = true;
  boot.loader.grub.device = "/dev/sda";
```

### Installing Vim

First connect to WiFi by running. From the TUI select connection and enter WiFi password.

```
sudo systemctl start NetworkManager  
sudo systemctl enable NetworkManager

sudo nmtui
# activate connection -> choose wifi -> enter password
```

Add the following lines 

"configuration.nix":
```
environment.systemPackages = with pkgs; [ vim ];
environment.variables.EDITOR = "vim";
```

This installs Vim and also makes it so when I run `sudo -e`, the editor that opens is Vim and not Nano. 

## Finish Installation

```
cd /mnt
sudo nixos-install
```

# Initial Configuring

## Flakes

Further reading: https://nixos-and-flakes.thiscute.world/nixos-with-flakes/start-using-home-manager

Inside `/etc/nixos`, we create a `flake.nix` file. If you have used Rust before, a `flake.nix`/`flake.lock` is analogous to a `Cargo.toml`/`Cargo.lock`. Our `flake.nix` will call our `configuration.nix` but also specify which version of Nixpkgs to use.
## Home Manager

Further reading: https://nixos-and-flakes.thiscute.world/nixos-with-flakes/start-using-home-manager

I use `configuration.nix` to specify packages and configurations I want applied system wide and `home.nix` to specify configurations to apply to just this user.

With Home Manager, I can install packages like so 

```
home.packages = with pkgs; [ noefetch git ];
```

I port over my Vim config using the `extraConfig` attribute

```
programs.vim = {
	enable = true;
	extraConfig = '' 
		set relativenumber
		set ai
		syntax on
		// ...
	''
}
```
## Remapping Caps Lock to Esc

Remapping Caps Lock to Esc was not very intuitive. When I searched this up, most results explained how to do it with Wayland or X11 but I needed it to work on console. 

You need to set `console.luseXkbCOnfig = true;` and set the configuration inside `services.xserver.xkb.options` despite having `services.xserver.enable = false;`

```
console = {
	useXkbConfig = true; 
};

services.xserver = {
	enable = false;
	xkb.options = "caps:escape";
};
```

## `ssh`

Further reading: https://wiki.nixos.org/wiki/SSH

I want to be able to `ssh` onto my NixOS computer from my MacBook.

I first set `services.openssh.enable = true;` in the `configuration.nix` and rebuild.The command `hostname -I` gives the IP address. From my Mac I can run `cat ~/.ssh/id_ed25519.pub | ssh owenyi@ip_address "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"`. Now that I've transferred over the `ssh` keys, I can disable password authentication so now only my MacBook can connect and no one else. 

On my NixOS machine I modify the "configuration.nix":

```
services.openssh = {
	enable = true;
	ports = [ 5432 ]; # or some other port that isn't the default 22. 
	settings = {
		PasswordAuthentication = false;
	    KbdInteractiveAuthentication = false;
	    PermitRootLogin = "no";
	    AllowUsers = [ "owenyi" ];
	};
};
```

On my MacBook I add the lines to `~/.ssh/config` 

```
Host nixos
  HostName $ip_address
  User owenyi
  Port $same_port_as_in_nixos_config
  IdentityFile ~/.ssh/id_ed25519
```

This way I can `ssh` with the command `ssh owenyi@nixos` instead of something like `ssh -p port owenyi@ip_address`. 

With `ssh` enabled, I run on my MacBook for example

```
scp 'owenyi@nixos:/etc/nixos/*' . 
```

Which grabs all my nixos config files as they are now and copies them to my MacBook.
# Frequently Used Commands

```
nixos-rebuild dry-build # dry run to show what packages will be downloaded
sudo nixos-rebuild test 
sudo nixos-rebuild switch
```

These commands apply changes to the configuration. `test` applies the changes but doesn't add a "generation". `switch` applies changes and adds a "generation". You can boot any previous "generation" from the boot menu. 

```
sudo nix-collect-garbage -d
```

The way NixOS applies changes is by installing everything in `/nix/store` and symlinking the appropriate packages into the current environment (among other thing such as setting environment variables). If I remove a package from my `home.nix` or `configuration.nix`, the package is still stored in `/nix/store`. `nix-collect-garbage` will delete these dangling packages.

```
nixos-option 
```

The `nixos-option` command is really great from discoverability aspect. This lists all the options that can be configured. 

You can traverse down the tree manually for example suppose `console` was in the attribute set printed above. Running `nixos-option console` will bring up attributes under `console`.





