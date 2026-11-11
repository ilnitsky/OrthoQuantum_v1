export const presets = {
 nucleolus:{label:'GO · Nucleolus',type:'go',input:'GO:0005730'},
 remodellers:{label:'Preset · Chromatin remodellers',type:'symbols',input:'SMARCA2 SMARCA4 SMARCA5 SMARCA1 CHD1 CHD2 CHD3 CHD4 CHD5 CHD6 CHD7 CHD8 CHD9 INO80 SRCAP EP400'.split(' ').join('\n')},
 readers:{label:'Preset · Chromatin readers',type:'symbols',input:'BRD2 BRD3 BRD4 BRDT BRD7 BRD9 BPTF CBX1 CBX3 CBX5 UHRF1 UHRF2'.split(' ').join('\n')},
 writers:{label:'Preset · Histone writers',type:'symbols',input:'KMT2A KMT2B KMT2C KMT2D SETD1A SETD1B SETD2 EHMT1 EHMT2 SUV39H1 SUV39H2 KAT2A KAT2B EP300 CREBBP'.split(' ').join('\n')},
 polycomb:{label:'Preset · PRC1 + PRC2',type:'symbols',input:'RING1 RNF2 BMI1 PCGF1 PCGF2 PCGF3 PCGF5 PCGF6 CBX2 CBX4 CBX6 CBX7 CBX8 PHC1 PHC2 PHC3 EZH1 EZH2 EED SUZ12 RBBP4 RBBP7 JARID2 AEBP2'.split(' ').join('\n')},
 erasers:{label:'Preset · Histone erasers',type:'symbols',input:'KDM1A KDM1B KDM2A KDM2B KDM3A KDM3B KDM4A KDM4B KDM4C KDM5A KDM5B KDM5C KDM6A KDM6B HDAC1 HDAC2 HDAC3 HDAC8 SIRT1 SIRT2 SIRT6'.split(' ').join('\n')},
 dna:{label:'Preset · DNA methylation machinery',type:'symbols',input:'DNMT1 DNMT3A DNMT3B DNMT3L TET1 TET2 TET3 UHRF1 MBD1 MBD2 MBD3 MBD4 MECP2'.split(' ').join('\n')}
};
