# Plant and observation hardening

These source changes affect future synthetic execution. They do not revise any
historical result, operating envelope, model artifact, acceptance decision, or
vehicle/tuning permission.

## Observation snapshots

`WorldObservation.metadata` and `TrafficActorState.metadata` take recursive
snapshots at construction. JSON scalar values, string-keyed dictionaries, lists,
and tuples are supported. Normal mutation of the snapshot raises `TypeError`.
Provider objects belong outside metadata; unsupported mutable objects are
rejected. `dataclasses.asdict` and JSON serialization remain supported.

The actors collection is copied to a tuple. A provider can update its own source
dictionaries between ticks without changing earlier trace observations.

## Explicit teacher-force reentry

Normal runs need no new plugin methods. Teacher forcing requires the vehicle
plant and both composed axes to explicitly declare
`supports_state_assimilation = True` and implement
`assimilate_state(state_before, state_after, control, world)`.

The hook consumes the forced interval while preserving the existing command
delay, filter, and controller-facing state history. The plugin author must define
what an externally imposed endpoint means for that particular model. Calling
`reset` or simply inventing missing response history is not valid assimilation.
The generic composition layer does not make that model-specific choice.

The loop verifies the forced endpoint clock, calls assimilation, and then stores
the marked teacher-forced step. Combined plants update their own current state
only after both axes finish. A hook failure invalidates the combined plant until
an explicit reset; partial history cannot silently resume. Unsupported adapters
are rejected before the teacher-force callback executes. Synthetic test adapters
demonstrate normal/forced/normal transitions with one initial reset.

Normal axis-step failures and invalid next-state construction also require a
reset before another step. Reset itself marks the combined plant ready only
after both axis resets succeed.

## Longitudinal integration and horizons

Constant braking integrates only up to the stop time and then holds position for
the remainder of the step. `accel_mps2` continues to describe the axis response
value, including a braking request at zero speed; the position/speed constraint
does not reset that axis response. Lateral position remains outside this model.

Runs use whole fixed control periods to cover the requested duration. The step
count rounds up noninteger durations, except for a quotient within four floating
point ULPs of an integer. Thus `(0.1 + 0.2)` at `dt=0.1` takes three periods;
`0.300000001` still takes four. Returned final time records the actual horizon.
