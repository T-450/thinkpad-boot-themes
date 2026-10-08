# thinkpad-boot-themes

ThinkPad look for the Limine boot menu and a matching Plymouth splash.

| Limine (mock-up, not a screenshot) | Plymouth |
| --- | --- |
| ![Limine](limine/preview.png) | ![Plymouth](plymouth/preview.png) |

## Limine

Targets Limine 12.x reading `/boot/limine.conf`. Copies the wallpaper to `/boot/limine/`, backs up the config and adds any missing theme keys after `default_entry:`. Safe to re-run. Runs `limine-snapper-sync` if installed.

```sh
sudo bash limine/apply-limine-theme.sh
```

Undo: `sudo cp -a /boot/limine.conf.bak-theme-<timestamp> /boot/limine.conf && sudo rm /boot/limine/thinkpad-wallpaper.png`

If `/boot/limine/limine.conf` exists, Limine reads it first; the script warns about it.

## Plymouth

Script-module theme `thinkpad-limine`. Backs up `/etc/plymouth/plymouthd.conf`, installs to `/usr/share/plymouth/themes/thinkpad-limine`, sets it as default and runs `mkinitcpio -P`.

```sh
sudo bash plymouth/install-plymouth-theme.sh
```

Undo: `sudo plymouth-set-default-theme <previous-theme> && sudo mkinitcpio -P && sudo rm -r /usr/share/plymouth/themes/thinkpad-limine`

## License

GPL-3.0. Artwork derived from the `thinkpad` theme of [distro-grub-themes](https://github.com/ahmedmoselhi/distro-grub-themes) v3.4 (GPL-3.0). ThinkPad is a trademark of Lenovo.
