import json
# TODO FIX:
# *not
# *adc, sbc, and, or ect
base = \
    {
        "CPU":
        {
            "Name": "PotaDOS",
            "Arch": "POTDOS",
            "Author": "Gwiezdny Kartofel - Lord225",
            "emulator": "potados_emulator",
            "time_per_cycle": 3.3,

            "ARGUMENTS": {
                "variants":
                {
                    "const16":
                    {
                        "pdec": {
                            "size": 2
                        },
                        "const": {
                            "size": 16
                        },
                        "dst": {
                            "size": 4
                        }
                    },
                    "branch":
                    {
                        "pridec": {
                            "size": 2
                        },
                        "secdec": {
                            "size": 3
                        },
                        "r2": {
                            "size": 4
                        },
                        "pad": {
                            "size": 1
                        },
                        "offset": {
                            "size": 8
                        },
                        "r1": {
                            "size": 4
                        },
                    },
                    "aluimm":
                    {
                        "pridec": {
                            "size": 2
                        },
                        "secdec": {
                            "size": 3
                        },
                        "r2": {
                            "size": 4
                        },
                        "I": {
                            "size": 1
                        },
                        "R1": {
                            "size": 8
                        },
                        "dst": {
                            "size": 4
                        }
                    },
                    "alufpu":
                    {
                        "pridec": {
                            "size": 2
                        },
                        "secdec": {
                            "size": 3
                        },
                        "r2": {
                            "size": 4
                        },
                        "flags": {
                            "size": 5
                        },
                        "r1": {
                            "size": 4
                        },
                        "dst": {
                            "size": 4
                        }
                    },
                    "indirectlsh":
                    {
                        "pridec": {
                            "size": 2
                        },
                        "secdec": {
                            "size": 3
                        },
                        "ptr": {
                            "size": 4
                        },
                        "3th": {
                            "size": 3
                        },
                        "lsh": {
                            "size": 2
                        },
                        "offset": {
                            "size": 4
                        },
                        "srcdst": {
                            "size": 4
                        }
                    },
                    "indirect":
                    {
                        "pridec": {
                            "size": 2
                        },
                        "secdec": {
                            "size": 3
                        },
                        "ptr": {
                            "size": 4
                        },
                        "3th": {
                            "size": 3
                        },
                        "offset": {
                            "size": 6
                        },
                        "srcdst": {
                            "size": 4
                        }
                    },
                    "other":
                    {
                        "pridec": {
                            "size": 2
                        },
                        "secdec": {
                            "size": 3
                        },
                        "src": {
                            "size": 4
                        },
                        "3th": {
                            "size": 5
                        },
                        "r1": {
                            "size": 4
                        },
                        "dst": {
                            "size": 4
                        }
                    },
                    "inject":
                    {
                        "value": {
                            "size": 22
                        }
                    }
                }
            },

            "ADRESSING":
            {
                "mode": "align",
                "bin_len": 22,
                "offset": 0
            },

            "DEFINES": [
                "__POTDOS__",
                ["SP", "15"],  # Stack Ptr
                ["PC", "7"],   # Program Counter
                ["PT", "1"],   # Offset Pointer 
                ["FL", "8"]    # Flags
            ],
            "KEYWORDS":{
                "CORE0":{
                    "offset":0,
                    "write":0
                }
            },
            "FILL":"nop",
            "COMMANDS": {},
            "MACROS":{},
            "SCHEMATIC":
            {
                "blank":"potados_blank.schem",
                "high":"minecraft:netherite_block",
                "low":"minecraft:redstone_block",
                "layout": 
                {
                    # block
                    "offset":[0, 0, 0],
                    "stride":[0, 0, 6],
                    "size": 32,
                    "layout": 
                    {
                        # floor 
                        "offset":[0, 0, 0],
                        "stride":[3, 0, 0],
                        "size": 32,
                        "layout":
                        {
                            # word
                            "offset":[0, 0, 0],
                            "stride":[0, 2, 0],
                            "size": 22,
                            "layout": None
                        }
                    }
                }
            }
        }
    }

#
# Others Part 1
#
cmds = \
{
    "nop": {
        "pattern": "nop",
        "command_layout": "const16",
        "bin": {
            "pdec": 0,
            "const": 0,
            "dst": 0
        }
    },
    "load imm": {
        "pattern": "mov reg[{dst:num}], {val:num}",
        "command_layout": "const16",
        "bin": {
            "pdec": 0,
            "const": "val",
            "dst": "dst"
        }
    },
    # Alias load imm
    "jmp": {
        "pattern": "jmp {label:label}", 
        "command_layout": "const16",
        "bin": {
            "pdec": 0,
            "const": "label",
            "dst": 7
        }
    },
    "mov": {
        "pattern": "mov reg[{dst:num}], {label:label}", 
        "command_layout": "const16",
        "bin": {
            "pdec": 0,
            "const": "label",
            "dst": "dst"
        }
    },
    "copy": {
        "pattern": "mov reg[{dst:num}], reg[{src:num}]", 
        "command_layout": "alufpu",
        "bin": {
            "pridec": 1,
            "secdec": 3,
            "r2": "src",
            "flags": 0,
            "4th": 3,
            "r1": 0,
            "dst": "dst"
        }
    },
    "call": {
        "pattern": "call {label:label}",
        "command_layout": "const16",
        "bin": {
            "pdec": 3,
            "const": "label",
            "dst": 7
        }
    },
    "ret":{
        "pattern": "ret",
        "command_layout": "other",
        "bin": {   
            "pridec": 1,
            "secdec": 0,
            "src": 0,
            "3th": 5,
            "4th": 0,
            "pad": 0,
            "dst":7
        }           
    }
}
base["CPU"]["COMMANDS"].update(cmds)

decoder = json.decoder.JSONDecoder()

#
# branches
#
branch ="""
{{
    "branch {cmd_name} {sub_name}":
    {{
        "pattern": "{cmd_name} reg[{{arg1:num}}], reg[{{arg2:num}}], {{offset:offset_label}}",
        "command_layout": "branch",
        "bin": {{
            "pridec": 2,
            "secdec": {value},
            "r2": "{arg2}",
            "offset": "offset",
            "r1": "{arg1}"
        }}
    }}
}}
"""
tokens = [
    ("jge", 0, True), 
    ("jl", 1, True), 
    ("je", 2, False), 
    ("jne", 3, False), 
    ("jae", 4, False), 
    ("jb", 5, False),
    # Rev args
    ("jg", 1, False), 
    ("ja", 5, True),

    ("jle", 0, False), 
    ("jbe", 4, True),
]

for token, value, rev in tokens:
    arg1, arg2 = ("arg2", "arg1") if rev else ("arg1", "arg2") 
    formated = decoder.decode(branch.format(cmd_name=token, value=value, arg1=arg1, arg2=arg2, sub_name= "imm" if rev else ""))
    base["CPU"]["COMMANDS"].update(formated)

#
# Branch IMM
#
branchimm ="""
{{
    "branch {cmd_name} {symbol}":
    {{
        "pattern": "{cmd_name} reg[1]{symbol}, reg[{{reg:num}}], {{offset:offset_label}}",
        "command_layout": "branch",
        "bin": {{
            "pridec": 2,
            "secdec": {value},
            "r2": "reg",
            "offset": "offset",
            "r1": {decoder}
        }}
    }}
}}
"""
base["CPU"]["COMMANDS"].update(decoder.decode(branchimm.format(cmd_name="jge", value=6, symbol="++", decoder=2)))
base["CPU"]["COMMANDS"].update(decoder.decode(branchimm.format(cmd_name="jge", value=6, symbol="--", decoder=1)))
base["CPU"]["COMMANDS"].update(decoder.decode(branchimm.format(cmd_name="jne", value=7, symbol="++", decoder=2)))
base["CPU"]["COMMANDS"].update(decoder.decode(branchimm.format(cmd_name="jne", value=7, symbol="--", decoder=1)))

#
# ALU PART 1
#
alulong = """
{{
    "{name}":
    {{
        "pattern": "{name} reg[{{dst:num}}], reg[{{arg1:num}}], reg[{{arg2:num}}]",
        "command_layout": "aluimm",
        "bin": {{
            "pridec": 1,
            "secdec": {sec},
            "r2": "arg1",
            "I": 0,
            "R1": "arg2 if arg2 < 16 else None",
            "dst": "dst"
        }}
    }},
    "{name} const":
    {{
        "pattern": "{name} reg[{{dst:num}}], reg[{{arg1:num}}], {{const:num}}",
        "command_layout": "aluimm",
        "bin": {{
            "pridec": 1,
            "secdec": {sec},
            "r2": "arg1",
            "I": 1,
            "R1": "const",
            "dst": "dst"
        }}
    }},
    "shortcut {name}":
    {{
        "pattern": "{name} reg[{{dst:num}}], reg[{{arg2:num}}]",
        "command_layout": "aluimm",
        "bin": {{
            "pridec": 1,
            "secdec": {sec},
            "r2": "dst",
            "I": 0,
            "R1": "arg2 if arg2 < 16 else None",
            "dst": "dst"
        }}
    }},
    "shortcut {name} const":
    {{
        "pattern": "{name} reg[{{dst:num}}], {{const:num}}",
        "command_layout": "aluimm",
        "bin": {{
            "pridec": 1,
            "secdec": {sec},
            "r2": "dst",
            "I": 1,
            "R1": "const",
            "dst": "dst"
        }}
    }}
}}
"""
tokens = [
    ("add", 1),
    ("sub", 2),
    ("arsh", 4),
    ("rsh", 5),
    ("lsh", 6),
    ("mul", 7),
]
for token, value in tokens:
    formated = decoder.decode(alulong.format(name=token, sec=value))
    base["CPU"]["COMMANDS"].update(formated)

#
# ALU PART 2 (AND FPU)
#
ops2 = """
{{
    "{name}":
    {{
        "pattern": "{name} reg[{{dst:num}}], reg[{{arg1:num}}], reg[{{arg2:num}}]",
        "command_layout": "alufpu",
        "bin": {{
            "pridec": 1,
            "secdec": {sec},
            "r2": "arg1",
            "flags": {flags},
            "r1": "arg2",
            "dst": "dst"
        }}
    }},
    "shortcut {name}":
    {{
        "pattern": "{name} reg[{{dst:num}}], reg[{{arg2:num}}]",
        "command_layout": "alufpu",
        "bin": {{
            "pridec": 1,
            "secdec": {sec},
            "r2": "dst",
            "flags": {flags},
            "r1": "arg2",
            "dst": "dst"
        }}
    }}
}}
"""
# 0 0    1
# 1 0    1
# 0 1    1
# 1 1    0 

tokens = [
    ("xor", 3, 8),  # N 0 ~A 0 ~B 0 xor 1 1000 # 8
    ("and", 3, 7), # N 1 ~A 1 ~B 1 or  0 0111 # 7
    ("or", 3, 0),   # N 0 ~A 0 ~B 0 or  0 0000 # 0
    ("fadd", 0, 1), # 00001 # 1
    ("fsub", 0, 2),
    ("fmul", 0, 3),
    ("fdiv", 0, 4),
    ("ftoi", 0, 5),
    ("itof", 0, 6),
    ("utof", 0, 7), 
    ("xnor", 3, 1), # N 1 ~A 0 ~B 0 xor 0 0001 # 1
    ("nand", 3, 14), # N 0 ~A 1 ~B 1 or  1 1110 # 14 
    ("nor", 3, 9),  # N 1 ~A 0 ~B 0 or  1 1001 # 9
]
for name, sec, flags in tokens:
    formated = decoder.decode(ops2.format(name=name, sec=sec, flags=flags))
    base["CPU"]["COMMANDS"].update(formated)

#
# loads and stores
#

def gen_base():
    return {
        "load ptr lsh":{
            "pattern": "mov reg[{dst:num}], ram[reg[{ptr:num}] + {lsh:num}*reg[8] + {offset:num}]",
            "command_layout":"indirectlsh",
            "bin": {
                "pridec": 1,
                "secdec": 0,
                "ptr": "ptr",
                "3th": 6,
                "lsh": "{1:0, 2:1, 4:2, 8:3}[lsh] if lsh in [1, 2, 4, 8] else None",
                "offset": "offset",
                "srcdst": "dst"
            }
        },
        "load ptr imm":{
            "pattern": "mov reg[{dst:num}], ram[reg[{ptr:num}] + {offset:num}]",
            "command_layout":"indirect",
            "bin": {
                "pridec": 1,
                "secdec": 0,
                "ptr": "ptr",
                "3th": 7,
                "offset": "offset",
                "srcdst": "dst"
            }
        },
        "store ptr lsh":{
            "pattern": "mov ram[reg[{ptr:num}] + {lsh:num}*reg[8] + {offset:num}], reg[{dst:num}]",
            "command_layout":"indirectlsh",
            "bin": {
                "pridec": 1,
                "secdec": 0,
                "ptr": "ptr",
                "3th": 4,
                "lsh": "{1:0, 2:1, 4:2, 8:3}[lsh] if lsh in [1, 2, 4, 8] else None",
                "offset": "offset",
                "srcdst": "dst"
            }
        },
        "store ptr imm":{
            "pattern": "mov ram[reg[{ptr:num}] + {offset:num}], reg[{dst:num}]",
            "command_layout":"indirect",
            "bin": {
                "pridec": 1,
                "secdec": 0,
                "ptr": "ptr",
                "3th": 5,
                "offset": "offset",
                "srcdst": "dst"
            }
        }
    }
macro_index = 0

def gen_macro_load(pattern, process: dict):
    global macro_index
    macro_index += 1

    if 'lsh' in process and process['lsh'] != '0':
        return gen_macro_load_lsh(pattern, process)
    else:
        process.pop('lsh', None)
        return gen_macro_load_imm(pattern, process)

def gen_macro_load_lsh(pattern, process):
    return {f"load lsh macro {macro_index}":{ 
             "pattern": f"mov reg[{{dst:token}}], ram[{pattern}]",
             "process": process,
             "expansion":["mov reg[{dst}], ram[reg[{ptr}] + {lsh}*reg[8] + {offset}]"]}}
def gen_macro_load_imm(pattern, process):
    return {f"load imm macro {macro_index}":{ 
             "pattern": f"mov reg[{{dst:token}}], ram[{pattern}]",
             "process": process,
             "expansion":["mov reg[{dst}], ram[reg[{ptr}] + {offset}]"]}}

def gen_macro_store(pattern, process: dict):
    global macro_index
    macro_index += 1

    if 'lsh' in process and process['lsh'] != '0':
        return gen_macro_store_lsh(pattern, process)
    else:
        process.pop('lsh', None)
        return gen_macro_store_imm(pattern, process)

def gen_macro_store_lsh(pattern, process):
    return {f"load lsh macro {macro_index}":{ 
             "pattern": f"mov ram[{pattern}], reg[{{dst:token}}]",
             "process": process,
             "expansion":["mov ram[reg[{ptr}] + {lsh}*reg[8] + {offset}], reg[{dst}]"]}}
def gen_macro_store_imm(pattern, process):
    return {f"load imm macro {macro_index}":{ 
             "pattern": f"mov ram[{pattern}], reg[{{dst:token}}]",
             "process": process,
             "expansion":["mov ram[reg[{ptr}] + {offset}], reg[{dst}]"]}}
base["CPU"]["COMMANDS"].update(gen_base())

def gen_all(gen_func):
    import itertools

    # base
    base["CPU"]["MACROS"].update(gen_func("reg[{ptr:token}]", {"offset":"0"}))
    # base + displ
    base["CPU"]["MACROS"].update(gen_func("{offset:token} + reg[{ptr:token}]", {"offset":"offset"}))
    # displ
    base["CPU"]["MACROS"].update(gen_func("{offset:token}", {"ptr":"0", "offset":"offset"}))
    # base + negative displ
    base["CPU"]["MACROS"].update(gen_func("reg[{ptr:token}] - {offset:token}", {"offset":"-int(offset)"}))
    base["CPU"]["MACROS"].update(gen_func("- {offset:token} + reg[{ptr:token}]", {"offset":"-int(offset)"}))
    # base + index + displ
    for lsh in [0, 1, 2, 4, 8]:
        for (a,b,c) in itertools.islice(itertools.permutations(["reg[{ptr:token}]", f"{lsh}*reg[8]", "{offset:token}"]), 1, None):
            base["CPU"]["MACROS"].update(gen_func(f"{a} + {b} + {c}", {"lsh":f"{lsh}", "offset":"offset"}))
    for (a,b,c) in itertools.permutations(["reg[{ptr:token}]", f"reg[8]", "{offset:token}"]):
            base["CPU"]["MACROS"].update(gen_func(f"{a} + {b} + {c}", {"lsh":"1", "offset":"offset"}))
    # base + index
    for lsh in [0, 1, 2, 4, 8]:
        for (a,b) in itertools.permutations(["reg[{ptr:token}]", f"{lsh}*reg[8]"]):
            base["CPU"]["MACROS"].update(gen_func(f"{a} + {b}", {"lsh":f"{lsh}", "offset":"0"}))
    for (a,b) in itertools.permutations(["reg[{ptr:token}]", "reg[8]"]):
        base["CPU"]["MACROS"].update(gen_func(f"{a} + {b}", {"lsh":"1", "offset":"0"}))
    # index
    for lsh in [0, 1, 2, 4, 8]:
        base["CPU"]["MACROS"].update(gen_func(f"{lsh}*reg[8]", {"ptr":"0", "offset":"0"}))
    # base + index + negative displ
    for lsh in [0, 1, 2, 4, 8]:
        for (a,b,c) in itertools.permutations(["+ reg[{ptr:token}]", f"+ {lsh}*reg[8]", "- {offset:token}"]):
            base["CPU"]["MACROS"].update(gen_func(f"{a.strip('+')} {b} {c}", { "lsh":f"{lsh}", "offset":"-int(offset)"}))
    for (a,b,c) in itertools.permutations(["+ reg[{ptr:token}]", f"+ reg[8]", "- {offset:token}"]):
            base["CPU"]["MACROS"].update(gen_func(f"{a.strip('+')} {b} {c}", { "lsh":"1", "offset":"-int(offset)"}))

gen_all(gen_macro_load)
gen_all(gen_macro_store)

base["CPU"]["MACROS"].update({f"store index 0":{ "pattern": "mov ram[reg[{ptr:token}] + 0*reg[8]+{offset:token}], reg[{dst:token}]", "process": {}, "expansion":["mov ram[reg[{ptr}] + {offset}], reg[{dst}]"]}})
base["CPU"]["MACROS"].update({f"load index 0": { "pattern": "mov reg[{dst:token}], ram[reg[{ptr:token}]+0*reg[8] + {offset:token}]", "process": {}, "expansion":["mov reg[{dst}], ram[reg[{ptr}] + {offset}]"]}})

#
# others
#
values = {
    "pop": {
        "pattern": "pop reg[{dst:num}]",
        "command_layout": "other",
        "bin": {
            "pridec": 1,
            "secdec": 0,
            "src": 0,
            "3th": 9,
            "r1": 0,
            "dst": "dst"
        }
    },
    "push": {
        "pattern": "push reg[{src:num}]",
        "command_layout": "other",
        "bin": {
            "pridec": 1,
            "secdec": 0,
            "src": "src",
            "3th": 10,
            "r1": 0,
            "dst": 0
        }
    },
    "int": {
        "pattern": "int {type:num}",
        "command_layout": "other",
        "bin": {
            "pridec": 1,
            "secdec": 0,
            "src": 0,
            "3th": 11,
            "r1": 0,
            "dst": "type"
        }
    },

    "not": {
        "pattern": "not reg[{dst:num}], reg[{src:num}]",
        "command_layout": "alufpu",
        "bin": {
            "pridec": 1,
            "secdec": 3,
            "r2": 0,
            "flags": 1,
            "4th": 1,
            "r1": "src",
            "dst": "dst"
        }
    },
    "inject":{
        "pattern": "inject {value:num}",
        "command_layout": "inject",
        "bin": {
            "value":"value"
        }
    },
    "inc": {
        "pattern": "inc reg[{target:num}]",
        "command_layout": "aluimm",
        "bin": {
            "pridec": 1,
            "secdec": 1,
            "r2": "target",
            "I": 1,
            "R1": 1,
            "dst": "target"
        }
    },
    "dec": {
        "pattern": "dec reg[{target:num}]",
        "command_layout": "aluimm",
        "bin": {
            "pridec": 1,
            "secdec": 2,
            "r2": "target",
            "I": 1,
            "R1": 1,
            "dst": "target"
        }
    }
}
base["CPU"]["COMMANDS"].update(values)

IOSCHEM="""
{{
    "{name}":{{
        "pattern": "{name} reg[{{srcdst:num}}]",
        "command_layout":"indirect",
        "bin": {{
            "pridec": 1,
            "secdec": 0,
            "ptr": 0,
            "3th": {ls},
            "offset": {address},
            "srcdst": "srcdst"
        }}
    }}
}}
"""

def add_io(name, is_load, address):
    formated = decoder.decode(IOSCHEM.format(name=name, ls = 4 if is_load else 2, address=address))
    base["CPU"]["COMMANDS"].update(formated)

add_io("print", True, 0x0005)
add_io("dbg", True, 0x0006)
add_io("clk set", True, 0x0001)
add_io("clk get", False, 0x0001)
add_io("tim set", True, 0x0002)
add_io("tim get", False, 0x0002)
add_io("tim state set", True, 0x0003)
add_io("tim state get", False, 0x0003)
add_io("gpu status", True, 0x000c)
add_io("gpu invoke", False, 0x000d)

with open('profiles/potados/potados.jsonc', 'w') as f:
    json.dump(base, f, indent=4)
