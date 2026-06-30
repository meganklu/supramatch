load .pdb
extract cavity, resname CV
alter name D, vdw=0.5
show_as surface, cavity
spectrum b, blue_white_red,cavity, minimum=-5.952864, maximum=-0.790349
ramp_new 'ramp', cavity, [-5.952864,-3.160094,-0.790349], ['blue','white','red']
recolor
