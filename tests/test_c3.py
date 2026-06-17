from CageCavityCalc.CageCavityCalc import cavity

cage_name = "../data/zd001_Picture_1"
grid_spacing = 0.5
distance_threshold_for_90_deg_angle = 2.0

cav = cavity()
cav.read_file(cage_name+".pdb")
window_radius = cav.calculate_window()
cav.distance_threshold_for_90_deg_angle = window_radius * distance_threshold_for_90_deg_angle
if cav.distance_threshold_for_90_deg_angle < 5:
    cav.distance_threshold_for_90_deg_angle = 5
cav.grid_spacing = float(grid_spacing)
cav.dummy_atom_radii = float(grid_spacing)
volume = cav.calculate_volume()
cav.print_to_file(cage_name+"_cavity.pdb")
cav.print_to_pymol(cage_name+"_cavity.pml")
cav.hydrophMethod = "Ghose" #Ghose or Crippen
cav.distance_function = "Fauchere" # Audry, Fauchere, Fauchere2, OnlyValues
cav.calculate_hydrophobicity()
cav.print_to_file(cage_name+"_cavity_hydrophobicity.pdb")
cav.print_to_pymol(cage_name+"_cavity_hydrophobicity.pml", 'h')
cav.calculate_esp() #If metals: cav.calculate_esp(metal_name="Pd", metal_charge=2)
cav.print_to_file(cage_name+"_cavity_esp.pdb")
cav.print_to_pymol(cage_name+"_cavity_esp.pml", "esp")
print("Cavity_volume= ", volume, " A3")
