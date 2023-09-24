if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.getcwd())

import typing
from bitvec import Binary, arithm as ops
from bitvec.alias import  u16, i16, u4, u6
import core.config as config
import core.error as error
import core.emulate as emulate
import numpy as np
import unittest
from core.profile.profile import load_profile_from_file

import core.quick as quick

class POTADOS_EMULATOR(emulate.EmulatorBase):
    DEBUG_HALT_ON_NOP = False
    INTERUPT_0_AS_INT = Binary("01 000 0000 01011 0000 0000", lenght=22).int()
    NOP_AS_INT = Binary("0 0000000000000000 0000", lenght=22).int()

    SP = 15
    PC = 7
    PT = 1
    FL = 8

    def __init__(self) -> None:
        self.regs = REGS(self)
        self.ram = RAM(self, None)
        self.rom = ROM(self, 1024)
        self.is_running_flag = True
        self.pc_modified = False


    def get_current_pos(self, chunk_name: typing.Optional[str]) -> int:
        return int(self.regs[self.PC])

    def is_running(self) -> bool:
        return self.is_running_flag

    def get_machine_cycles(self) -> int:
        return 1

    def next_tick(self,) -> typing.Optional[str]:
        command = self.rom[self.get_current_pos(None)]
        
        # nop
        if command == POTADOS_EMULATOR.NOP_AS_INT:
            self.nop()
            self.regs.increment_pc()
            return

        # int 0 (early stop)
        if command == POTADOS_EMULATOR.INTERUPT_0_AS_INT:
            self.halt()
            self.regs.increment_pc()
            return

        # parse command
        pri_decoder = int(command[20:22])  # primary decoder 2 bit
        destination = int(command[0:4])    # dst register 4 bit

        if pri_decoder == 0:   # load imm
            constant = Binary(command[4:20]) # const 16 bit

            if destination == self.PC:
                self.jump(constant)  # type: ignore
            else:
                self.load_imm(constant, destination)
        elif pri_decoder == 3: # call
            constant = Binary(command[4:20]) # const 16 bit
            self.call(constant)
        elif pri_decoder == 2: # jumps
            sec_decoder = int(command[17:20])
            r2_value = int(command[13:17])
            offset = Binary(command[4:12])
            r1_value = int(command[0:4])

            offset = ops.pad_sign_extend(offset, 16)

            if sec_decoder == 0:   # jge
                self.jge(r1_value, r2_value, offset)
            elif sec_decoder == 1: # jl
                self.jl(r1_value, r2_value, offset)
            elif sec_decoder == 2: # je
                self.je(r1_value, r2_value, offset)
            elif sec_decoder == 3: # jne
                self.jne(r1_value, r2_value, offset)
            elif sec_decoder == 4: # jae
                self.jae(r1_value, r2_value, offset)
            elif sec_decoder == 5: # jb 
                self.jb(r1_value, r2_value, offset)
            elif sec_decoder == 6: # jge imm
                self.jge_inc_dec("++" if r1_value == 2 else "--", r2_value, offset)
            elif sec_decoder == 7: # je imm
                self.jne_inc_dec("++" if r1_value == 2 else "--", r2_value, offset)
            else:
                raise error.EmulationError("Unreachable")
        else:                      # rest
            flags       = command[8:13]
            sec_decoder = command[17:20].int()

            if sec_decoder in [1, 2, 4, 5, 6, 7]: # alu long
                self.alu_long(sec_decoder, destination, command)
            elif sec_decoder == 3:                # alu short / fpu
                self.alu_short(destination, flags, command) 
            elif sec_decoder == 0:      # other
                dec = flags[2:].int()
                r1    = command[4:8].int()
                r2    = command[13:17].int()
                fpu   = command[8:11].int()

                if dec == 0 or dec == 1:
                    self.fpu(r1, r2, destination, fpu)
                elif dec == 6:        # load ptr lsh
                    lsh = command[8:10].int()
                    offset = command[4:8].int()
                    self.load_ptr_lsh(2**lsh, offset, r2, destination)
                elif dec == 7:        # load ptr imm
                    offset = command[4:10].int()
                    self.load_ptr_imm(offset, r2, destination)
                elif dec == 4:        # store ptr lsh
                    lsh = command[8:10].int()
                    offset = command[4:8].int()
                    self.store_ptr_lsh(2**lsh, offset, r2, destination)
                elif dec == 5:        # store ptr imm
                    offset = command[4:10].int()
                    self.store_ptr_imm(offset, r2, destination)
                elif flags == 9:        # pop
                    self.pop(destination)
                elif flags == 6:        # push
                    self.push(r1)
                elif flags == 7:        # converts & interupt
                    third = command[8:10].int()
                    if third == 0:
                        self.ftoi(r1, destination)
                    elif third == 1:
                        self.itof(r1, destination)
                    elif third == 2:
                        self.utof(r1, destination)
                    elif third == 3:
                        self.interupt(destination)
                    else:
                        raise error.EmulationError("Unrachable 1")
                elif flags == 10:        # push
                    self.push(r2)
                elif flags == 11:        # int
                    self.interupt(destination)
                else:
                    raise error.EmulationError("Invalid Command")
            else:
                raise error.EmulationError("Unrachable 3")
        
        self.regs.increment_pc()

    
    def load(self, address):
        return self.ram[address]
    def store(self, address, value):
        self.ram[address] = value

    def alu_long(self, sec_decoder: int, destination: int, command: Binary):
        I = command[12]
        r1_value = command[4:12]        # 8 bit
        r2_value = command[13:17].int() # 4 bit

        if I:
            imm = ops.pad_sign_extend(r1_value, 16) # type: ignore
            if sec_decoder == 1:
                self.alu_add_imm(imm, r2_value, destination)
            elif sec_decoder == 2:
                self.alu_sub_imm(imm, r2_value, destination)
            elif sec_decoder == 4:
                self.alu_arsh_imm(imm, r2_value, destination)
            elif sec_decoder == 5:
                self.alu_rsh_imm(imm, r2_value, destination)
            elif sec_decoder == 6:
                self.alu_lsh_imm(imm, r2_value, destination)
            elif sec_decoder == 7:
                self.alu_mul_imm(imm, r2_value, destination)
            else: 
                raise error.EmulationError("Unreachable")
        else:
            r1 = int(r1_value[:4]) # type: ignore
            if sec_decoder == 1:
                self.alu_add_reg(r1, r2_value, destination)
            elif sec_decoder == 2:
                self.alu_sub_reg(r1, r2_value, destination)
            elif sec_decoder == 4:
                self.alu_arsh_reg(r1, r2_value, destination)
            elif sec_decoder == 5:
                self.alu_lsh_reg(r1, r2_value, destination)
            elif sec_decoder == 6:
                self.alu_rsh_reg(r1, r2_value, destination)
            elif sec_decoder == 7:
                self.alu_mul_reg(r1, r2_value, destination)
            else:
                raise error.EmulationError("Unreachable")
    def alu_short(self, destination: int, flags: Binary, command: Binary):
        r1 = int(command[4:8])
        r2 = int(command[13:17])

        op_flag      = flags[3]
        neg_r2_flag  = flags[2]
        neg_r1_flag  = flags[1]
        neg_out_flag = flags[0]

        if op_flag:  # xor
            if neg_out_flag:
                self.alu_xnor(r1, r2, destination, "~" if neg_r1_flag else "", "~" if neg_r2_flag else "")
            else:
                self.alu_xor(r1, r2, destination, "~" if neg_r1_flag else "", "~" if neg_r2_flag else "")
        else:        # or
            if neg_out_flag:
                self.alu_nor(r1, r2, destination, "~" if neg_r1_flag else "", "~" if neg_r2_flag else "")
            else:
                self.alu_or(r1, r2, destination, "~" if neg_r1_flag else "", "~" if neg_r2_flag else "")
    
    def fpu(self, r1: int, r2: int, destination: int, cmd: int):
        if cmd == 0:
            pass
        if cmd == 1:
            self.fadd(r1, r2, destination)
        elif cmd == 2:
            self.fsub(r1, r2, destination)
        elif cmd == 3:
            self.fmul(r1, r2, destination)
        elif cmd == 4:
            self.fdiv(r1, r2, destination)
        elif cmd == 5:
            self.ftoi(r1, destination)
        elif cmd == 6:
            self.itof(r1, destination)
        elif cmd == 7:
            self.utof(r1, destination)
        else:
            raise error.EmulationError("Unreachable")
        
    
    ##################
    #    FL update   #
    ##################
    
    def update_flags_for_jump(self, r1, r2):
        pass

    def update_flags_for_add_sub(self, flags: ops.Flags):
        self.regs[self.FL][0] = flags.zeroflag
        self.regs[self.FL][1] = flags.overflow #TODO check if it works fine for subtraction (tzn czy to jest borrow flag)
        self.regs[self.FL][2] = flags.signflag
        self.regs[self.FL][3] = flags.overflow

    ###############
    #     nops    #
    ###############

    @emulate.log_disassembly(format='nop')
    def nop(self):
        if self.DEBUG_HALT_ON_NOP:
            print("Halting on nop")
            self.halt()

    @emulate.log_disassembly(format='int 0')   
    def halt(self):
        self.is_running_flag = False

    ########
    # ints #
    ########

    @emulate.log_disassembly(format='int {i}')
    def interupt(self, i):
        if i == 0:
            self.is_running_flag = False
        elif i == 1:
            pass
        elif i == 2:
            pass


    #######
    # FPU #
    #######
    def cast_to_fp16(self, value: Binary) -> float:
        return np.frombuffer(value.raw_bytes, dtype='float16')[0]
    def cast_from_fp16(self, value: float) -> Binary:
        return Binary(np.array([value], dtype='float16').tobytes(), lenght=16)
    @emulate.log_disassembly(format='fadd reg[{dst}], reg[{r1}], reg[{r2}]')
    def fadd(self, r1, r2, dst):
        a = self.cast_to_fp16(self.regs[r1])
        b = self.cast_to_fp16(self.regs[r2])

        self.regs[dst] = ops.cast(self.cast_from_fp16(a+b), 'unsigned')

    @emulate.log_disassembly(format='fsub reg[{dst}], reg[{r1}], reg[{r2}]')
    def fsub(self, r1, r2, dst):
        a = self.cast_to_fp16(self.regs[r1])
        b = self.cast_to_fp16(self.regs[r2])

        self.regs[dst] = ops.cast(self.cast_from_fp16(b-a), 'unsigned') 
    
    @emulate.log_disassembly(format='fmul reg[{dst}], reg[{r1}], reg[{r2}]')
    def fmul(self, r1, r2, dst):
        a = self.cast_to_fp16(self.regs[r1])
        b = self.cast_to_fp16(self.regs[r2])

        self.regs[dst] = ops.cast(self.cast_from_fp16(a*b), 'unsigned')

    @emulate.log_disassembly(format='fdiv reg[{dst}], reg[{r1}], reg[{r2}]')
    def fdiv(self, r1, r2, dst):
        a = self.cast_to_fp16(self.regs[r1])
        b = self.cast_to_fp16(self.regs[r2])
        
        self.regs[dst] = ops.cast(self.cast_from_fp16(a/b), 'unsigned')

    @emulate.log_disassembly(format='ftoi reg[{dst}], reg[{src}]')
    def ftoi(self, src, dst):
        self.regs[dst] = u16(int(self.cast_to_fp16(self.regs[src])))

    @emulate.log_disassembly(format='itof reg[{dst}], reg[{src}]')
    def itof(self, src, dst):
        val = self.cast_from_fp16(ops.cast(self.regs[src], 'signed').int())

        self.regs[dst] = u16(val)
    
    @emulate.log_disassembly(format='utof reg[{dst}], reg[{src}]')
    def utof(self, src, dst):
        val = self.cast_from_fp16(ops.cast(self.regs[src], 'unsigned').int())

        self.regs[dst] = u16(val)

    #########
    # stack #
    #########

    @emulate.log_disassembly(format='pop reg[{dst}]')
    def pop(self, dst):
        self.regs[self.SP] = self.regs[self.SP] - 1
        self.regs[dst] = self.load(int(self.regs[self.SP]))

    @emulate.log_disassembly(format='push reg[{src}]')
    def push(self, src):
        self.store(int(self.regs[self.SP]), self.regs[src])
        self.regs[self.SP] = self.regs[self.SP] + 1

    ###########
    # ptr ops #
    ###########

    @emulate.log_disassembly(format='mov reg[{dst}], ram[reg[{ptr}] + {lsh}*reg[1] + {offset}]')
    def load_ptr_lsh(self, lsh, offset, ptr, dst):
        ptr_val = self.regs[ptr]
        
        offset = ops.pad_sign_extend(u4(offset), 16)

        address = ops.wrapping_mul(self.regs[self.PT], lsh) + offset + ptr_val

        self.regs[dst] = self.load(address)

    @emulate.log_disassembly(format='mov reg[{dst}], ram[reg[{ptr}] + {offset}]')
    def load_ptr_imm(self, offset, ptr, dst):
        ptr_val = self.regs[ptr]
        
        offset = ops.pad_sign_extend(u6(offset), 16)

        address = offset + ptr_val

        self.regs[dst] = self.load(address)

    @emulate.log_disassembly(format='mov ram[reg[{ptr}] + {lsh}*reg[1] + {offset}], reg[{src}]')
    def store_ptr_lsh(self, lsh, offset, ptr, src):
        ptr_val = self.regs[ptr]
        src_val = self.regs[src]

        offset = ops.pad_sign_extend(u4(offset), 16)
        
        address = ops.wrapping_mul(self.regs[self.PT], Binary(lsh, lenght=2)) + offset + ptr_val

        self.store(address, src_val)
    
    @emulate.log_disassembly(format='mov ram[reg[{ptr}] + {offset}], reg[{src}]')
    def store_ptr_imm(self, offset, ptr, src):
        ptr_val = self.regs[ptr]
        src_val = self.regs[src]
        
        offset = ops.pad_sign_extend(u6(offset), 16)
        
        address = offset + ptr_val

        self.store(address, src_val)

    ############
    # ALU LONG #
    ############
    ######################
    # add implementation #
    ######################

    def alu_add(self, imm_r1: Binary, imm_r2: Binary, dst: int):
        r1 = ops.cast(imm_r1.extended_low(), 'unsigned')
        r2 = ops.cast(imm_r2.extended_low(), 'unsigned')
        
        out, flags = ops.flaged_add(r1, r2)

        self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    @emulate.log_disassembly(format='add reg[{dst}], reg[{r2_reg}], {r1_imm}')
    def alu_add_imm(self, r1_imm: Binary, r2_reg: int, dst: int):
        r2_imm = self.regs[r2_reg]

        self.alu_add(r1_imm, r2_imm, dst)
    @emulate.log_disassembly(format='add reg[{dst}], reg[{r2_reg}], reg[{r1_reg}]')
    def alu_add_reg(self, r1_reg: int, r2_reg: int, dst: int):
        r1_imm = self.regs[r1_reg]
        r2_imm = self.regs[r2_reg]

        self.alu_add(r1_imm, r2_imm, dst)

    ######################
    # sub implementation #
    ######################

    def alu_sub(self, imm_r1: Binary, imm_r2: Binary, dst: int):
        r1 = ops.cast(imm_r1.extended_low(), 'unsigned')
        r2 = ops.cast(imm_r2.extended_low(), 'unsigned')
        
        out, flags = ops.flaged_sub(r2, r1)

        self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    @emulate.log_disassembly(format='sub reg[{dst}], reg[{r2_reg}], {r1_imm}')
    def alu_sub_imm(self, r1_imm: Binary, r2_reg: int, dst: int):
        r2_imm = self.regs[r2_reg]

        self.alu_sub(r1_imm, r2_imm, dst)
    @emulate.log_disassembly(format='sub reg[{dst}], reg[{r2_reg}], reg[{r1_reg}]')
    def alu_sub_reg(self, r1_reg: int, r2_reg: int, dst: int):
        r1_imm = self.regs[r1_reg]
        r2_imm = self.regs[r2_reg]

        self.alu_sub(r1_imm, r2_imm, dst)
        
    #######################
    # arsh implementation #
    #######################

    def alu_arsh(self, imm_r1: Binary, imm_r2: Binary, dst: int):
        r1 = ops.cast(imm_r1.extended_low(), 'unsigned')
        r2 = ops.cast(imm_r2.extended_low(), 'unsigned')
        
        out = ops.arithmetic_wrapping_rsh(r1, r2)

        #self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    @emulate.log_disassembly(format='arsh reg[{dst}], reg[{r2_reg}], {r1_imm}')
    def alu_arsh_imm(self, r1_imm: Binary, r2_reg: int, dst: int):
        r2_imm = self.regs[r2_reg]

        self.alu_arsh(r1_imm, r2_imm, dst)
    @emulate.log_disassembly(format='arsh reg[{dst}], reg[{r2_reg}], reg[{r1_reg}]')
    def alu_arsh_reg(self, r1_reg: int, r2_reg: int, dst: int):
        r1_imm = self.regs[r1_reg]
        r2_imm = self.regs[r2_reg]

        self.alu_arsh(r1_imm, r2_imm, dst)
    
    ######################
    # rsh implementation #
    ######################

    def alu_rsh(self, imm_r1: Binary, imm_r2: Binary, dst: int):
        r1 = ops.cast(imm_r1.extended_low(), 'unsigned')
        r2 = ops.cast(imm_r2.extended_low(), 'unsigned')
        
        out = ops.logical_wrapping_rsh(r2, r1)

        #self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    @emulate.log_disassembly(format='rsh reg[{dst}], reg[{r2_reg}], {r1_imm}')
    def alu_rsh_imm(self, r1_imm: Binary, r2_reg: int, dst: int):
        r2_imm = self.regs[r2_reg]

        self.alu_rsh(r1_imm, r2_imm, dst)
    @emulate.log_disassembly(format='rsh reg[{dst}], reg[{r2_reg}], reg[{r1_reg}]')
    def alu_rsh_reg(self, r1_reg: int, r2_reg: int, dst: int):
        r1_imm = self.regs[r1_reg]
        r2_imm = self.regs[r2_reg]

        self.alu_rsh(r1_imm, r2_imm, dst)

    ######################
    # lsh implementation #
    ######################

    def alu_lsh(self, imm_r1: Binary, imm_r2: Binary, dst: int):
        r1 = ops.cast(imm_r1.extended_low(), 'unsigned')
        r2 = ops.cast(imm_r2.extended_low(), 'unsigned')
        
        out = ops.wrapping_lsh(r2, r1)

        #self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    @emulate.log_disassembly(format='lsh reg[{dst}], reg[{r2_reg}], {r1_imm}')
    def alu_lsh_imm(self, r1_imm: Binary, r2_reg: int, dst: int):
        r2_imm = self.regs[r2_reg]

        self.alu_lsh(r1_imm, r2_imm, dst)
    @emulate.log_disassembly(format='lsh reg[{dst}], reg[{r2_reg}], reg[{r1_reg}]')
    def alu_lsh_reg(self, r1_reg: int, r2_reg: int, dst: int):
        r1_imm = self.regs[r1_reg]
        r2_imm = self.regs[r2_reg]

        self.alu_lsh(r1_imm, r2_imm, dst)

    ######################
    # mul implementation #
    ######################

    def alu_mul(self, imm_r1: Binary, imm_r2: Binary, dst: int):
        r1 = ops.cast(imm_r1.extended_low(), 'unsigned')
        r2 = ops.cast(imm_r2.extended_low(), 'unsigned')
        
        out, _ = ops.overflowing_mul(r2, r1)

        #self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    @emulate.log_disassembly(format='mul reg[{dst}], reg[{r2_reg}], {r1_imm}')
    def alu_mul_imm(self, r1_imm: Binary, r2_reg: int, dst: int):
        r2_imm = self.regs[r2_reg]

        self.alu_mul(r1_imm, r2_imm, dst)
    @emulate.log_disassembly(format='mul reg[{dst}], reg[{r2_reg}], reg[{r1_reg}]')
    def alu_mul_reg(self, r1_reg: int, r2_reg: int, dst: int):
        r1_imm = self.regs[r1_reg]
        r2_imm = self.regs[r2_reg]

        self.alu_mul(r1_imm, r2_imm, dst)
    
    #############
    # ALU SHORT #
    #############
    
    @emulate.log_disassembly(format='adc reg[{dst}], reg[{r2}], reg[{r1}]')
    def alu_adc(self, r1: int, r2: int, dst: int):
        r1_imm = self.regs[r1]
        r2_imm = self.regs[r2]
        carry = self.regs[self.FL][1]
        
        out, flags = ops.flaged_add(r2_imm, r1_imm + 1 if carry else 0)
        
        self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    @emulate.log_disassembly(format='sbc reg[{dst}], reg[{r2}], reg[{r1}]')
    def alu_sbc(self, r1: int, r2: int, dst: int):
        r1_imm = self.regs[r1]
        r2_imm = self.regs[r2]
        carry = self.regs[self.FL][1]
        
        out, flags = ops.flaged_sub(r2_imm, r1_imm + 1 if carry else 0)
        
        self.update_flags_for_add_sub(flags)

        self.regs[dst] = out
    
    @emulate.log_disassembly(format='xor reg[{dst}], {r1_neg}reg[{r2}], {r2_neg}reg[{r1}]')
    def alu_xor(self, r1: int, r2: int, dst: int, r1_neg: str, r2_neg: str):
        r1_imm = self.regs[r1] if r1_neg == "" else ops.bitwise_not(self.regs[r1])
        r2_imm = self.regs[r2] if r2_neg == "" else ops.bitwise_not(self.regs[r1])
        
        self.regs[dst] = ops.bitwise_xor(r2_imm, r1_imm)
    @emulate.log_disassembly(format='xnor reg[{dst}], {r1_neg}reg[{r2}], {r2_neg}reg[{r1}]')
    def alu_xnor(self, r1: int, r2: int, dst: int, r1_neg: str, r2_neg: str):
        r1_imm = self.regs[r1] if r1_neg == "" else ops.bitwise_not(self.regs[r1])
        r2_imm = self.regs[r2] if r2_neg == "" else ops.bitwise_not(self.regs[r1])
        
        self.regs[dst] = ops.bitwise_not(ops.bitwise_xor(r2_imm, r1_imm))

    @emulate.log_disassembly(format='or reg[{dst}], {r1_neg}reg[{r2}], {r2_neg}reg[{r1}]')
    def alu_or(self, r1: int, r2: int, dst: int, r1_neg: str, r2_neg: str):
        r1_imm = self.regs[r1] if r1_neg == "" else ops.bitwise_not(self.regs[r1])
        r2_imm = self.regs[r2] if r2_neg == "" else ops.bitwise_not(self.regs[r1])
        
        self.regs[dst] = ops.bitwise_or(r2_imm, r1_imm)
    @emulate.log_disassembly(format='nor reg[{dst}], {r1_neg}reg[{r2}], {r2_neg}reg[{r1}]')
    def alu_nor(self, r1: int, r2: int, dst: int, r1_neg: str, r2_neg: str):
        r1_imm = self.regs[r1] if r1_neg == "" else ops.bitwise_not(self.regs[r1])
        r2_imm = self.regs[r2] if r2_neg == "" else ops.bitwise_not(self.regs[r1])
        
        self.regs[dst] = ops.bitwise_not(ops.bitwise_or(r2_imm, r1_imm))
    
    
    ######################
    # mov implementation #
    ######################

    @emulate.log_disassembly(format='mov reg[{dst}], {const}')
    def load_imm(self, const: Binary, dst: int):
        self.regs[dst] = const
    @emulate.log_disassembly(format='jmp {const}')
    def jump(self, const: Binary):
        self.regs[self.PC] = const
    @emulate.log_disassembly(format='call {const}')
    def call(self, const: Binary):
        self.store(int(self.regs[self.SP]), self.regs[self.PC] + 1)
        self.regs[self.SP] += 1
        self.regs[self.PC] = const
    

    ########################
    # cjmps implementation #
    ########################
    
    @emulate.log_disassembly(format='jge reg[{r1_value}], reg[{r2_value}], {offset}')
    def jge(self, r1_value, r2_value, offset):
        r1 = ops.cast(self.regs[r1_value], 'signed')
        r2 = ops.cast(self.regs[r2_value], 'signed')

        self.update_flags_for_jump(r1, r2)

        if r1 >= r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')
    @emulate.log_disassembly(format='jl reg[{r1_value}], reg[{r2_value}], {offset}')
    def jl(self, r1_value, r2_value, offset):
        r1 = ops.cast(self.regs[r1_value], 'signed')
        r2 = ops.cast(self.regs[r2_value], 'signed')

        self.update_flags_for_jump(r1, r2)

        if r1 < r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')
    @emulate.log_disassembly(format='je reg[{r1_value}], reg[{r2_value}], {offset}')
    def je(self, r1_value, r2_value, offset):
        r1 = self.regs[r1_value]
        r2 = self.regs[r2_value]

        self.update_flags_for_jump(r1, r2)

        if r1 == r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')
    @emulate.log_disassembly(format='jne reg[{r1_value}], reg[{r2_value}], {offset}')
    def jne(self, r1_value, r2_value, offset):
        r1 = self.regs[r1_value]
        r2 = self.regs[r2_value]

        self.update_flags_for_jump(r1, r2)

        if r1 != r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')
    @emulate.log_disassembly(format='jae reg[{r1_value}], reg[{r2_value}], {offset}')
    def jae(self, r1_value, r2_value, offset):
        r1 = self.regs[r1_value]
        r2 = self.regs[r2_value]

        self.update_flags_for_jump(r1, r2)

        if r1 >= r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')
    @emulate.log_disassembly(format='jb reg[{r1_value}], reg[{r2_value}], {offset}')
    def jb(self, r1_value, r2_value, offset):
        r1 = self.regs[r1_value]
        r2 = self.regs[r2_value]

        self.update_flags_for_jump(r1, r2)

        if r1 < r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')

    # Version 11
    @emulate.log_disassembly(format='jge reg[1]{r1_value}, reg[{r2_value}], {offset}')
    def jge_inc_dec(self, r1_value, r2_value, offset):
        if r1_value == "++":
            self.regs[1] += 1
        elif r1_value == "--":
            self.regs[1] -= 1
        
        r1 = ops.cast(self.regs[1], 'signed')
        r2 = ops.cast(self.regs[r2_value], 'signed')

        self.update_flags_for_jump(r1, r2)

        if r1 >= r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')
    @emulate.log_disassembly(format='jne reg[1]{r1_value}, reg[{r2_value}], {offset}')
    def jne_inc_dec(self, r1_value, r2_value, offset):
        if r1_value == "++":
            self.regs[1] += 1
        elif r1_value == "--":
            self.regs[1] -= 1
        
        r1 = ops.cast(self.regs[1], 'signed')
        r2 = ops.cast(self.regs[r2_value], 'signed')

        self.update_flags_for_jump(r1, r2)

        if r1 != r2:
            self.regs[self.PC] = self.regs[self.PC] + ops.cast(offset, 'unsigned')



    def write_memory(self, chunk_name: typing.Optional[str], type: emulate.DataTypes, data: dict):
        if type == emulate.DataTypes.DATA:
            for address, value in data.items():
                self.ram[address] = value
        if type == emulate.DataTypes.PROGRAM:
            self.rom.program_rom(data)

    def exec_command(self, chunk_name: typing.Optional[str], method_name: str, args: typing.List) -> typing.Any:
        method = self.__getattribute__(method_name)
        return method(*args)

    ################## 
    # DEBUG COMMANDS #
    ##################

    def enable_dummy_jumps(self):
        self.DEBUG_IGNORE_JUMPS = True
    def disable_dummy_jumps(self):
        self.DEBUG_IGNORE_JUMPS = False
    def enable_dummy_reg_writes(self):
        self.regs.enable_dummy_reg_writes()
    def disable_dummy_reg_writes(self):
        self.regs.disable_dummy_reg_writes()
    def enable_ram_bus_logging(self):
        self.ram.DEBUG_LOG_RAM_MOVMENT = True
    def disable_ram_bus_logging(self):
        self.ram.DEBUG_LOG_RAM_MOVMENT = False
    def enable_ram_freeze(self):
        self.ram.DEBUG_FREEZE_RAM_WRITES = True
    def disable_ram_freeze(self):
        self.ram.DEBUG_FREEZE_RAM_WRITES = False

    def get_ram_ref(self):
        return self.ram.ram
    def get_regs_ref(self):
        return self.regs.regs


class REGS:
    DEBUG_FREEZE_WRITES = False

    def __init__(self, potados: POTADOS_EMULATOR):
        self.potados = potados
        self.regs = [u16(0) for _ in range(0, 16)]
        self.pc_modified = False
    def __getitem__(self, key: int) -> Binary: 
        if key == 0:
            return u16(0)
        return self.regs[key]
    def __setitem__(self, key: int, val: Binary):
        if self.DEBUG_FREEZE_WRITES:
            return
        if key == 0:
            return

        if len(val) != 16:
            val = val.extended_low()
        val = ops.cast(val, 'unsigned')

        if key == self.potados.PC:
            self.pc_modified = True

        self.regs[key] = val
    def __str__(self) -> str:
        return str(self.regs)
    def enable_dummy_reg_writes(self):
        self.DEBUG_FREEZE_WRITES = True
    def disable_dummy_reg_writes(self):
        self.DEBUG_FREEZE_WRITES = False
    def increment_pc(self):
        if not self.pc_modified:
            self.regs[self.potados.PC] += 1
        self.pc_modified = False

class IO:
    def __init__(self, potados: typing.Optional[POTADOS_EMULATOR]):
        self.potados = potados if potados is not None else POTADOS_EMULATOR()
    def Null(self, val) -> int:
        return 0
    def ClockFlag(self, val) -> int:
        return 0
    def TimerValue(self, val) -> int:
        raise error.EmulationError("TODO")
    def TimerFlags(self, val) -> int:
        raise error.EmulationError("TODO")
    def Out0(self, val: Binary) -> int:
        return 0
    def Out1(self, val: Binary) -> int:
        print(f"\tBINARY DISPLAY  -  {val.bin()}  -")
        return 0
    def Out2(self, val: Binary) -> int:
        print(f"\tDBG  -  {int(val)}  -  {Binary(val).hex()} ")
        return 0
    def Out3(self, val) -> int:
        return 0

    ADDRESSES = [Null, ClockFlag, TimerValue, TimerFlags, Out0, Out1, Out2, Out3]        


class RAM:
    DEBUG_LOG_RAM_MOVMENT = False 
    DEBUG_FREEZE_RAM_WRITES = False
    DEBUG_RISE_ON_OUT_OF_BOUNDS = False

    def __init__(self, potados: typing.Optional[POTADOS_EMULATOR], ram: typing.Optional[np.ndarray]) -> None:
        self.cpu = potados
        if ram is None:
            self.ram: np.ndarray = np.zeros((256), dtype='uint16')
        else:
            self.ram: np.ndarray = ram.astype('uint16')
        self.ram = self.ram[:256]
        self.io = IO(potados)

    
    def __getitem__(self, key: typing.Union[int, Binary]) -> Binary:
        key = int(key)

        bus = u16(0)
        if key < 0x0100:
            bus = self.io_get(key)
        if key >= 0x0200:
            if self.DEBUG_RISE_ON_OUT_OF_BOUNDS:
                raise error.EmulationError(f"Ram address out of bounds: {key}")
            bus = u16(0)
        else:
            bus = u16(int(self.ram[key-0x0100]))

        if self.DEBUG_LOG_RAM_MOVMENT:
            print(f"READ {key} (BUS: {bus.extended_low()})")
        return bus
        
    def __setitem__(self, key: typing.Union[int, Binary], val: typing.Union[int, Binary]):
        key = int(key)
        if not isinstance(val, Binary):
            val = Binary(val, lenght=16)
        if key < 0x0100:
            if self.DEBUG_LOG_RAM_MOVMENT:
                print(f"WRITE: {key} (BUS: {val.extended_low()})")
            self.io_set(key, val)
        if key >= 0x0200:
            if self.DEBUG_RISE_ON_OUT_OF_BOUNDS:
                raise error.EmulationError(f"Ram address out of bounds: {key}, trying write value: {val}")
            return
        if self.DEBUG_FREEZE_RAM_WRITES:
            return
        if self.DEBUG_LOG_RAM_MOVMENT:
                print(f"WRITE: {key} (BUS: {val.extended_low()})")
        self.ram[key-0x0100] = int(val.extended_low())


    def io_set(self, index: int, val: Binary):
        if index > 0x0100:
            raise

        if index <= 0x001f:
            self.io.ADDRESSES[index](self.io, val)
        
        if index == 6:
            print(f"[PotaDOS] [DBG] {val.int()}")

    def io_get(self, index: int) -> Binary:
        if index > 0x0100:
            raise

        if index <= 0x001f:
            return self.io.ADDRESSES[index](self.io, 0)
        
        return u16(0)
    
    def enable_ram_bus_logging(self):
        self.DEBUG_LOG_RAM_MOVMENT = True
    def disable_ram_bus_logging(self):
        self.DEBUG_LOG_RAM_MOVMENT = False

    def enable_ram_freeze(self):
        self.DEBUG_FREEZE_RAM_WRITES = True
    def disable_ram_freeze(self):
        self.DEBUG_FREEZE_RAM_WRITES = False


class ROM:
    def __init__(self, potados: typing.Optional[POTADOS_EMULATOR], ROM_SIZE) -> None: 
        self.cpu = potados
        self.rom = np.zeros((ROM_SIZE), dtype='uint32')

    def program_rom(self, data: dict):
        for address, value in data.items():
            self.rom[address] = value
    
    def __getitem__(self, address: int) -> Binary:
        return Binary(int(self.rom[address]), lenght=22)
    
def get_emulator() -> POTADOS_EMULATOR:
    return POTADOS_EMULATOR()


# To pulloff tests just run 
# python -m unittest profiles\potados_emulator.py 
# from \Lord-s-asm-for-mc\ 
# (or debug this file inside vs code)

class RAM_TESTS(unittest.TestCase):
    def test_get_ram_default(self):
        ram = RAM(None, None)

        self.assertEqual(ram[0x0100], u16(0))
        self.assertEqual(ram[0x0101], u16(0))
        self.assertEqual(ram[0x01FF], u16(0))
        self.assertEqual(ram[0x0200], u16(0))
        self.assertEqual(ram.ram.shape, (256,))

    def test_get_ram_ones(self):
        ram = RAM(None, np.ones((256)))

        self.assertEqual(ram[0x0100], u16(1))
        self.assertEqual(ram[0x0101], u16(1))
        self.assertEqual(ram[0x01FF], u16(1))
        self.assertEqual(ram[0x0200], u16(0))
        self.assertEqual(ram.ram.shape, (256,))

    def test_get_ram_ones_from_bigger_array(self):
        ram = RAM(None, np.ones((1024)))

        self.assertEqual(ram[0x0100], u16(1))
        self.assertEqual(ram[0x0101], u16(1))
        self.assertEqual(ram[0x01FF], u16(1))
        self.assertEqual(ram[0x0200], u16(0))
        self.assertEqual(ram.ram.shape, (256,))
    
    def test_set_ram(self):
        ram = RAM(None, np.ones((256)))

        ram[0x0100] = 255
        self.assertEqual(ram[0x0100], u16(255))
        ram[0x0100] = -1
        self.assertEqual(ram[0x0100], u16(2**16-1)) #u16 max 
        ram[0x01FF] = 255
        self.assertEqual(ram[0x01FF], u16(255))
        ram[0x0200] = 255
        self.assertEqual(ram[0x0200], u16(0))

    def test_get_io(self):
        pass
    def test_set_io(self):
        pass

class ROM_TESTS(unittest.TestCase):
    def test_rom(self):
        rom = ROM(None, 4096)

        rom.program_rom({0: 0, 1: 1, 2: 2, 3: 3})

        self.assertEqual(rom[0], Binary(0, lenght=22))
        self.assertEqual(rom[1], Binary(1, lenght=22))
        self.assertEqual(rom[2], Binary(2, lenght=22))
        self.assertEqual(rom[3], Binary(3, lenght=22))
        
        self.assertEqual(rom.rom.shape, (4096,))


class REGS_TESTS(unittest.TestCase):
    def test_read_write(self):
        potados = POTADOS_EMULATOR()
        regs = potados.regs

        for i in range(16):
            self.assertEqual(regs[i], u16(0))
        
        for i in range(16):
            regs[i] = i16(1)
        
        self.assertEqual(regs[0], u16(0))
        self.assertEqual(regs[1], u16(1))
        self.assertEqual(regs[2], u16(1))
        self.assertEqual(regs[3], u16(1))
        self.assertEqual(regs[15], u16(1))
        self.assertEqual(regs[8], u16(1))
        self.assertEqual(regs[7], u16(1))

        regs.enable_dummy_reg_writes()

        for i in range(16):
            regs[i] = i16(255)

        self.assertEqual(regs[0], u16(0))
        self.assertEqual(regs[1], u16(1))
        self.assertEqual(regs[2], u16(1))
        self.assertEqual(regs[3], u16(1))
        self.assertEqual(regs[15], u16(1))
        self.assertEqual(regs[8], u16(1))
        self.assertEqual(regs[7], u16(1))

        regs.disable_dummy_reg_writes()

    def test_pc_modified(self):
        potados = POTADOS_EMULATOR()
        regs = potados.regs

        self.assertEqual(regs[potados.PC], u16(0))
        regs[potados.PC] = i16(1)

        self.assertTrue(regs.pc_modified)
        
        self.assertEqual(regs[potados.PC], u16(1))
        regs.increment_pc()

        self.assertEqual(regs[potados.PC], u16(1))
        regs.increment_pc()

        self.assertEqual(regs[potados.PC], u16(2))
        regs.increment_pc()

        self.assertEqual(regs[potados.PC], u16(3))


        


class POTADOS_TESTS(unittest.TestCase):
    def test_mov(self):
        potados = POTADOS_EMULATOR()

        potados.load_imm(u16(1), 1)

        self.assertEqual(potados.regs[1], u16(1))

        potados.load_imm(u16(1), 0)

        self.assertEqual(potados.regs[0], u16(0))
        
    def test_jump(self): 
        potados = POTADOS_EMULATOR()

        potados.jump(u16(2))

        self.assertEqual(potados.regs[potados.PC], u16(2))

        potados.next_tick()

        self.assertEqual(potados.regs[potados.PC], u16(2))

        potados.next_tick()

        self.assertEqual(potados.regs[potados.PC], u16(3))
        
    def test_call(self):
        potados = POTADOS_EMULATOR()

        potados.regs[potados.SP] = u16(0x0100)   # type: ignore

        potados.jump(u16(1))

        potados.next_tick()

        potados.call(u16(32))

        potados.next_tick()

        self.assertEqual(potados.regs[potados.SP], u16(0x0100+1))
        self.assertEqual(potados.regs[potados.PC], u16(32))
        self.assertEqual(potados.ram[0x0100], u16(2)) # Next address after call

    def test_cjumps(self):
        potados = POTADOS_EMULATOR()

        potados.regs[1] = u16(1)
        potados.regs[2] = u16(3)

        potados.regs[potados.PC] = u16(10)

        potados.jge(2, 1, u16(10))
        self.assertEqual(potados.regs[potados.PC], 20)
        #self.assertEqual(potados.regs[potados.FL], u16('01010'))

        potados.regs[potados.PC] = u16(10)
        
        potados.jge(1, 2, u16(10))
        self.assertEqual(potados.regs[potados.PC], 10)
        #self.assertEqual(potados.regs[potados.FL], u16('10100'))

        potados.regs[3] = i16(-1)
        potados.regs[4] = i16(1)

        potados.jge(3, 4, i16(-10))
        self.assertEqual(potados.regs[potados.PC], 10)
        #self.assertEqual(potados.regs[potados.FL], u16('10100'))

        potados.jl(4, 3, u16(10))
        self.assertEqual(potados.regs[potados.PC], 10)
        #self.assertEqual(potados.regs[potados.FL], u16('01010'))
        
        potados.je(3, 3, u16(10))
        self.assertEqual(potados.regs[potados.PC], 20)
        #self.assertEqual(potados.regs[potados.FL], u16('01101'))

        # -1 casted to unsigned (all ones) >= 1 casted to unsigned 
        potados.jae(3, 4, u16(10))
        self.assertEqual(potados.regs[potados.PC], 30)
    def test_cjumps2(self):
        R1 = list(range(-5, 0)) + list(range(5))
        R2 = list(range(-5, 0)) + list(range(5))

        def get(r1, r2):
            potados = POTADOS_EMULATOR()
            potados.regs[1] = Binary(r1, lenght=16)
            potados.regs[2] = Binary(r2, lenght=16)
            potados.regs[potados.PC] = u16(10)
            return potados

        for r1 in R1:
            for r2 in R2:
                potados = get(r1, r2)
                potados.jge(1, 2, i16(-10))
                self.assertEqual(potados.regs[potados.PC]==0, r1>=r2, f'{r1} >= {r2} but {potados.regs[potados.PC]}')

                potados = get(r1, r2)
                potados.je(1, 2, i16(-10))
                self.assertEqual(potados.regs[potados.PC]==0, r1==r2, f'{r1} == {r2} but {potados.regs[potados.PC]}')

                potados = get(r1, r2)
                potados.jne(1, 2, i16(-10))
                self.assertEqual(potados.regs[potados.PC]==0, r1!=r2, f'{r1} != {r2} but {potados.regs[potados.PC]}')

                potados = get(r1, r2)
                potados.jae(1, 2, i16(-10))
                self.assertEqual(potados.regs[potados.PC]==0, ops.cast(i16(r1), 'unsigned')>=ops.cast(i16(r2), 'unsigned'))

                potados = get(r1, r2)
                potados.jb(1, 2, i16(-10))
                self.assertEqual(potados.regs[potados.PC]==0, ops.cast(i16(r1), 'unsigned')<ops.cast(i16(r2), 'unsigned'))

class POTADOS_COMPILATION_TESTS(unittest.TestCase):
    profile = load_profile_from_file('potados', load_emulator=False)
    def test_compile(self):
        output, context = quick.translate([
            'mov reg[1], 1',
            'add reg[1], reg[2], reg[3]',
            'LABEL:',
            'jne reg[1], reg[2], LABEL',
            'mov reg[1], ram[reg[2]+3]',
        ], 
        POTADOS_COMPILATION_TESTS.profile)

        parsed = [line.parsed_command for line in output]

        self.assertEqual(parsed, 
            [
                {'const16': {'pdec': 0, 'const': 1, 'dst': 1}}, 
                {'aluimm': {'pridec': 1, 'secdec': 1, 'r2': 2, 'I': 0, 'R1': 3, 'dst': 1}}, 
                {'branch': {'pridec': 2, 'secdec': 3, 'r2': 2, 'pad': 0, 'offset': 0, 'r1': 1}}, 
                {'indirect': {'pridec': 1, 'secdec': 0, 'ptr': 2, '3th': 7, 'offset': 3, 'srcdst': 1}},
            ]
        )

        self.assertEqual(context.labels, {'LABEL': 3})
        self.assertEqual(context.physical_adresses, {'LABEL': 2})

    def test_compile_to_binary(self):
        output, _ = quick.translate([
            'mov reg[1], 1',
            'add reg[1], reg[2], 1',
        ], 
        POTADOS_COMPILATION_TESTS.profile)

        EXPECTED = [int(Binary("00  00000000 00000001  0001", 22)), int(Binary("01 001  0010 1 00000001 0001", 22))]

        gathered, _ = quick.gather_instructions(output, POTADOS_COMPILATION_TESTS.profile.adressing)

        self.assertEqual(gathered, {0: [EXPECTED[0]], 1: [EXPECTED[1]]})

        packed = quick.pack_adresses(gathered)

        self.assertEqual(packed, {0: EXPECTED[0], 1: EXPECTED[1]})

    def run_emulation(self, potados: POTADOS_EMULATOR, program : typing.List[str], limit = 1000):
        output, _ = quick.translate(program, POTADOS_COMPILATION_TESTS.profile)

        gathered, _ = quick.gather_instructions(output, POTADOS_COMPILATION_TESTS.profile.adressing)
        packed = quick.pack_adresses(gathered)

        potados.rom.program_rom(packed)

        for _ in range(limit):
            potados.next_tick()
            if not potados.is_running():
                break
        else:
            raise Exception(f'Program did not finish within {limit} ticks')

        return potados

    def test_fibonacci(self):
        potados = POTADOS_EMULATOR()
        FIBONACCI_CODE = [
            'mov reg[1], 1',
            'mov reg[2], 1',
            'mov reg[4], 15',
            'mov reg[5], 0',
            'LABEL:',
            'add reg[3], reg[1], reg[2]',
            'mov reg[1], reg[2]',
            'mov reg[2], reg[3]',
            'inc reg[5]',
            'jne reg[5], reg[4], LABEL',
            'int 0'
        ]
        
        try:
            potados = self.run_emulation(potados, FIBONACCI_CODE, 1000)
        except Exception as e:
            raise Exception(f'Fibonacci failed: {e}')

        # fibonacii is 1 1 2 3 5 8 13 21 34 55 89 144 233 377 610 987 1597 2584 4181 6765 
        #                                                         ^^^ ^^^^
        #                  1 2 3 4 5  6  7  8  9  19  11  12  13  14  15 
        self.assertEqual(potados.regs[1], 987)
        self.assertEqual(potados.regs[2], 1597)
        self.assertEqual(potados.regs[3], 1597)
        self.assertEqual(potados.regs[4], 15)
        self.assertEqual(potados.regs[5], 15)
        self.assertEqual(potados.regs[potados.PC], 10)

    def test_memcpy(self):
        potados = POTADOS_EMULATOR()
        MEMCPY_CODE = [
            'mov reg[1], 0x0100',
            'add reg[2], reg[1], 0x0010',
            'add reg[3], reg[1], 0x0010',
            'MEMCPY_loop:',
            'mov reg[4], ram[reg[1]]',
            'mov ram[reg[3]], reg[4]', 
            'inc reg[3]',
            'jne reg[1]++, reg[2], MEMCPY_loop',
            'int 0'
        ]
        for i in range(0, 16):
            potados.ram[0x0100+i] = i

        try:
            potados = self.run_emulation(potados, MEMCPY_CODE, 1000)
        except Exception as e:
            raise Exception(f'Memcpy failed: {e}')
        
        for i in range(0, 16):
            self.assertEqual(potados.ram[0x0100+i], potados.ram[0x0100+0x0010+i])

    def test_fibonacci_floats(self):
        potados = POTADOS_EMULATOR()
        FIBONACCI_CODE = [
                'mov reg[1], 0',
                'mov reg[2], 0',
                'mov reg[3], 1',
                'mov reg[4], 8',
                'mov reg[5], 0x5640', # 100.0f16
                'LOOP:',
                'add reg[2], reg[2], reg[3]',
                #'dbg reg[2]',
                'add reg[3], reg[3], reg[2]',
                #'dbg reg[3]',
                'jne reg[1]++, reg[4], LOOP',
                'itof reg[2], reg[2]',
                'itof reg[3], reg[3]',
                'fdiv reg[1], reg[2], reg[3]',
                'fmul reg[1], reg[1], reg[5]',
                'ftoi reg[1], reg[1]',
                #'dbg reg[1]',
                'int 0',
        ]
        
        try:
            potados = self.run_emulation(potados, FIBONACCI_CODE, 1000)
        except Exception as e:
            raise Exception(f'Fibonacci failed: {e}')

        self.assertEqual(potados.regs[1], 161)


if __name__ == "__main__":
    unittest.main()
    