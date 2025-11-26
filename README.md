# headscale-mullvad
*Automatically create Wireguard exit nodes in your Headscale tailnet*

# Requirements
- Headscale running on PR [#2892](https://github.com/juanfont/headscale/pull/2892)
- Mullvad account

# Overview
This small Python script automatically creates Mullvad Wireguard-only nodes in your Headscale tailnet & connects your devices with them.

# Usage
First, you'll have to configure the required environment variables in `.env.example` and move the file to `.env`.

## Nix
```bash
$ nix shell .#headscale-mullvad
```

## Python
```bash
$ pip install -r requirements.txt
$ python3 -m src.headscale_mullvad.main [COMMAND]
```

# Commands
## 1. Add relays
This registers Mullvad relays as nodes in Headscale.

### Add all relays
```bash
$ headscale-mullvad relay add --id $USER_ID
  Registering 500 relays ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```
*You can also use `--name` to specify a user by name.*

### Add relays located in specific countries
```bash
$ headscale-mullvad relay add --id $USER_ID --countries de,es
[00:00:00] INFO     Fetching Mullvad relays                                 
  Registering 10 relays ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

## 2. Connect nodes to relays
Once relays are added, you can grant specific nodes access to them and set up authentication with Mullvad automatically.

```bash
$ headscale-mullvad node add --id $NODE_ID
[00:00:00] INFO     Adding node abc to Mullvad                 
[00:00:00] INFO     Creating relay connections                                
  Creating 10 connections ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```
*You can also use `--name` to specify a node by name.*

## 3. List nodes & relays
### Relays
View all registered Mullvad relays.
```bash
$ headscale-mullvad relay list
                   Mullvad relays
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ ID        ┃ Name             ┃ Country ┃ City    ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ 100000001 │ mv-cy-nic-wg-001 │ Cyprus  │ Nicosia │
│ 100000002 │ mv-cy-nic-wg-002 │ Cyprus  │ Nicosia │
└───────────┴──────────────────┴─────────┴─────────┘
```

### Nodes
Check which nodes have access to the relays.
```bash
$ headscale-mullvad node list
            Nodes
┏━━━━┳━━━━━━┳━━━━━━┳━━━━━━━━┓
┃ ID ┃ Name ┃ User ┃ Access ┃
┡━━━━╇━━━━━━╇━━━━━━╇━━━━━━━━┩
│ 1  │ abc  │ foo  │ Yes    │
│ 2  │ xyz  │ bar  │ No     │
└────┴──────┴──────┴────────┘
```

## 4. Cleanup
### Revoke access to relays for a node
This will revoke access to all relays for a specific node. 
```bash
$ headscale-mullvad node delete --id $NODE_ID
[00:00:00] INFO     Deleting connections for node abc
  Deleting 10 connections ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

### Remove relays (and their connections)
This will delete relays and any connections to them.

```bash
$ headscale-mullvad relay delete --countries de,es
  Deleting 10 connections ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
  Deleting 10 relays ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```
*Omit `--countries` to delete all relays.*
