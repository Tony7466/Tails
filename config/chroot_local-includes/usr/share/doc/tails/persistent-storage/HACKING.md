# Adding new Persistent Storage features

Take these steps to add a new preset feature to the Persistent Storage:

1. Add a new `Feature` subclass to
   [config/chroot_local-includes/usr/lib/python3/dist-packages/tps/configuration/features.py](../../../../lib/python3/dist-packages/tps/configuration/features.py).

2. Add a new `Feature` subclass to
   [config/chroot_local-includes/usr/lib/python3/dist-packages/tps_frontend/views/features_view.py](../../../../lib/python3/dist-packages/tps_frontend/views/features_view.py)

3. Add a new `HdyActionRow` child to the `GtkListBox` of the
   corresponding section you want to add the feature to.

4. If the new feature needs any setup or teardown code, put a shell script
   in a subdirectory named after the new feature in
   [config/chroot_local-includes/usr/local/lib/persistent-storage/on-activated-hooks](../../../../local/lib/persistent-storage/on-activated-hooks)
   or
   [config/chroot_local-includes/usr/local/lib/persistent-storage/on-deactivated-hooks](../../../../local/lib/persistent-storage/on-deactivated-hooks).

   Note that's is possible that on-activated hooks are run multiple times
   without the on-deactivated hooks being run in between, so they must
   handle that case gracefully.
