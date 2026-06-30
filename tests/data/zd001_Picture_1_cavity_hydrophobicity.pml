load .pdb
extract cavity, resname CV
alter name D, vdw=0.5
show_as surface, cavity
spectrum b, blue_white_red,cavity, minimum=-0.003733, maximum=0.199423
ramp_new 'ramp', cavity, [-0.003733,0.050295,0.199423], ['blue','white','red']
recolor
