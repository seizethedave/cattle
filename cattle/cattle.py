

def run_config(cfg, dry_run):
    deps = getattr(cfg, 'deps', None)
    steps = getattr(cfg, 'steps', None)

    if steps is None:
        raise Exception("The config file doesn't define a steps attribute.")

    if dry_run:
        for step in steps:
            print(f"> {step.__class__.__name__}:")
            for c in step.dry_run():
                print(f"   > {c}")
    else:
        for step in steps:
            step.run()
