# headscale-mullvad
*Automatically create Wireguard exit nodes in your Headscale tailnet*

# Requirements
- Headscale running on PR [#2892](https://github.com/juanfont/headscale/pull/2892)
- Mullvad account

# Overview
This small Python script automatically creates Mullvad Wireguard-only nodes in your Headscale tailnet & connects your devices with them.

# Usage
First, you'll have to configure the required environment variables in `.env.example` and move the file to `.env`.

## Create all relays
```bash
$ python3 main.py -i $USER_ID create-relays
  Registering 500 relays ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

## Only create relays located in specific countries
```bash
$ python3 main.py -i $USER_ID create-relays -f de,es
  Registering 60 relays ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

## Create connections for a node
```bash
$ python3 main.py -i $USER_ID create-connections $NODE_ID
21:49:41 Creating connections for node 'foo' ...
  Connecting 60 peers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

## Clean up all relays & connections
```bash
$ python3 main.py -i $USER_ID clean
Deleting 500 connections ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Deleting 500 peers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

## Clean up relays (& connections) from specific countries
```bash
$ python3 main.py -i $USER_ID clean -f de,es
Deleting 60 connections ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Deleting 60 peers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```
