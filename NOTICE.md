# Public Release Notice

This repository is a sanitized public release of a larger private research project.

## Deliberately excluded

The public history must not contain:

- raw `rlog` / `qlog` files or vehicle video;
- real route identifiers or precise driving-location metadata;
- comma device hostnames, IP addresses or device IDs;
- SSH private/public key material or private key paths;
- personal computer usernames or absolute home/work paths;
- private observability evidence that directly identifies a device or route;
- credentials, tokens, cookies, API keys, or secrets.

Synthetic examples and non-identifying aggregate research summaries may be published.

## Upstream projects

Carrot/openpilot and any external simulation backends are separate upstream projects. This repository does not vendor their complete source trees. Their names, trademarks, code and licenses remain subject to their respective upstream terms.

## Repository license status

A redistribution license for this repository's own code has not yet been selected by the repository owner. Until a license is explicitly added, normal copyright rules apply. Public visibility on GitHub should not be interpreted as an additional license grant.

## Safety scope

The code in this repository is intended for offline simulation, research and validation infrastructure. It is not a real-road safety certification and does not authorize automated parameter tuning or real-vehicle writes.
