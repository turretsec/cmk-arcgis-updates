# Checkmk ArcGIS Enterprise Patch Update Plugin

[![License: GPL v2](https://img.shields.io/badge/License-GPLv2-blue.svg)](LICENSE)
[![Checkmk](https://img.shields.io/badge/Checkmk-2.3.0p1+-brightgreen.svg)](https://checkmk.com/)
[![ArcGIS Enterprise](https://img.shields.io/badge/ArcGIS%20Enterprise-11.1%2B-blue.svg)](https://enterprise.arcgis.com/)
[![Windows](https://img.shields.io/badge/Agent-Windows-informational.svg)](https://checkmk.com/)

A Checkmk agent plugin for monitoring ArcGIS Enterprise components for available patches.

An addition to the [cmk-arcgis](https://github.com/turretsec/cmk-arcgis) special agent plugin.

## Features

- Discovers all patchable ArcGIS Enterprise components from the Windows registry automatically
- Compares installed patch QFE_IDs against Esri's patch notification feed
- One service per discovered component - no manual configuration of what is installed
- Immediately alerts CRIT on any missing security patch
- Configurable WARN threshold for non-critical available patches
- Configurable CRIT threshold for overdue patches by age in days
- Patch feed cached locally - survives feed outages and uses stale cache as fallback
- Configurable feed URL for internal mirrors or air-gapped environments
- Deployed and configured via the Checkmk Agent Bakery

## How it works

The agent plugin runs on each Windows host where ArcGIS Enterprise components are installed. It enumerates `HKLM\SOFTWARE\ESRI`, discovers patchable components by checking for Esri's `QFEPatchFinder` and `QFEARP` registry markers, and compares each component's installed patch QFE_IDs against Esri's patch notification feed.

One service is created per discovered component on the host where it is installed.

```
ArcGIS Server host
    -> ArcGIS Server Patch Status

ArcGIS Portal host
    -> ArcGIS Portal Patch Status

ArcGIS Data Store host
    -> ArcGIS Data Store Patch Status
```

Hosts with multiple components installed receive one service per component.

## Requirements

- Checkmk 2.3.0p1+
- Windows Server (any version supported by ArcGIS Enterprise 11.1+)
- ArcGIS Enterprise 11.1+
- The monitored host must be able to reach `content.esri.com` for the patch feed, or an internal mirror must be configured

## Installation

### GUI

1. Go to **Setup -> Maintenance -> Extension packages**.
2. Upload the `.mkp` file.
3. Enable the package.
4. Activate changes.

### Command line

```
mkp add cmk-arcgis-updates-<version>.mkp
mkp enable arcgis_updates <version>
cmk -R
```

Validate the plugin after installation:

```
cmk-validate-plugins
```

## Setup

1. Create a rule under **Setup -> Agents -> Agent rules -> ArcGIS Enterprise: Patch Update Check**.
2. Assign the rule to your ArcGIS Enterprise hosts or host group.
3. Bake and deploy the updated agent package.
4. Run service discovery on each ArcGIS host.

No credentials are required. The plugin reads the Windows registry and fetches the public Esri patch feed.

## Configuration

### Agent Bakery rule

Found under **Setup -> Agents -> Agent rules -> ArcGIS Enterprise: Patch Update Check**.

All settings are optional. Defaults are used for anything left unconfigured.

| Setting | Description | Default |
|---|---|---|
| Patch feed URL | URL for the Esri patch notification JSON feed. Override for internal mirrors. | `https://content.esri.com/patch_notification/patches.json` |
| Patch feed cache TTL | Seconds to cache the feed locally before re-fetching | `3600` |
| Feed request timeout | HTTP timeout in seconds when fetching the patch feed | `15` |

### Service monitoring rule

Found under **Setup -> Service monitoring rules -> Applications -> ArcGIS Enterprise: Patch Status**.

| Setting | Description | Default |
|---|---|---|
| Warn when non-critical patches are available | Emit WARN when patches are available but not security-critical | enabled |
| Days before CRIT for overdue patches | Emit CRIT when the oldest unapplied patch exceeds this age | `90` |

Security patches always cause CRIT regardless of threshold configuration.

## Discovered services

| Service | Description |
|---|---|
| `ArcGIS Server Patch Status` | Patch status for ArcGIS Server |
| `ArcGIS Portal Patch Status` | Patch status for Portal for ArcGIS |
| `ArcGIS Data Store Patch Status` | Patch status for ArcGIS Data Store |
| `ArcGIS GeoEvent Server Patch Status` | Patch status for ArcGIS GeoEvent Server *(unverified - see [known limitations](#known-limitations))* |
| `ArcGIS Web Adaptor Patch Status` | Patch status for ArcGIS Web Adaptor *(unverified)* |
| `ArcGIS Notebook Server Patch Status` | Patch status for ArcGIS Notebook Server *(unverified)* |
| `ArcGIS Mission Server Patch Status` | Patch status for ArcGIS Mission Server *(unverified)* |
| `ArcGIS Video Server Patch Status` | Patch status for ArcGIS Video Server *(unverified)* |

Service output examples:

```
ArcGIS Server Patch Status     OK      v11.5 - Up to date (8/8)
ArcGIS Portal Patch Status     WARN    v11.5 - 3 patches available
ArcGIS Data Store Patch Status CRIT    v11.5 - 1 security patch missing
```

## Check parameters

Check parameter rules are found under **Setup -> Service monitoring rules -> Applications -> ArcGIS Enterprise: Patch Status**.

The rule supports `HostAndItemCondition`, so thresholds can be scoped to specific hosts or individual component services.

## Troubleshooting

### Run the plugin manually on a Windows host

```
"C:\ProgramData\checkmk\agent\modules\python-3\python.exe" ^
  "C:\ProgramData\checkmk\agent\plugins\arcgis_updates.checkmk.py"
```

The plugin writes the `<<<arcgis_updates>>>` section to stdout. If no components are found the section will contain an empty components list.

### Common issues

**No services discovered**

Verify that ArcGIS Enterprise components are installed and that the host has the `QFEPatchFinder` or `QFEARP` values present under `HKLM\SOFTWARE\ESRI\<component>`. Run the plugin manually and inspect the JSON output.

**Patch feed unavailable**

The service will report WARN with the error message. The plugin uses a local cache as fallback. Set a custom `patches_url` in the bakery rule if the host cannot reach `content.esri.com` directly.

**Service shows "No patches in feed for this version"**

The installed component version is not yet listed in the Esri patch feed. This is normal for very recently released versions. The service stays OK and will self-resolve once Esri publishes patches for that version.

## Known limitations

- Windows only. ArcGIS Enterprise on Linux stores component information in flat config files rather than the registry and is not currently supported.
- Tested against ArcGIS Enterprise 11.5 and Checkmk 2.5.x.
- Registry key patterns and QFE prefixes for GeoEvent Server, Web Adaptor, Notebook Server, Mission Server, Video Server, and Knowledge Server have not been verified against real installations. These components are discovered automatically if they have patches applied (the QFE prefix is read directly from the registry). Zero-patch installs of these components use unverified fallback patterns and may not be discovered correctly. See the open issue for how to contribute verification data.

## License

This project is licensed under the GNU General Public License v2.0 only. See [LICENSE](LICENSE).

This project is an independent Checkmk extension and is not affiliated with or endorsed by Checkmk GmbH or Esri. Checkmk and ArcGIS Enterprise are licensed separately by their respective owners.