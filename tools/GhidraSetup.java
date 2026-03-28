// Ghidra headless script: seed known entry points and force disassembly for 8051 ROM
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class GhidraSetup extends GhidraScript {
    @Override
    public void run() throws Exception {
        AddressFactory af = currentProgram.getAddressFactory();
        AddressSpace space = af.getDefaultAddressSpace();
        FunctionManager fm = currentProgram.getFunctionManager();
        SymbolTable st = currentProgram.getSymbolTable();

        // Known MS2107 ROM entry points and functions
        String[][] knownFuncs = {
            {"0x0000", "reset_vector"},
            {"0x0003", "ext0_isr"},
            {"0x000b", "timer0_isr"},
            {"0x0013", "ext1_isr"},
            {"0x001b", "timer1_isr"},
            {"0x0023", "serial_isr"},
            {"0x1f17", "copy_vid_pid_from_eeprom"},
            {"0x5323", "i2c_write_byte"},
            {"0x54ae", "usb_irq_handler"},
            {"0x5934", "i2c_read_byte"},
            {"0x6656", "eeprom_reload"},
            {"0x68bd", "i2c_start"},
            {"0x6b5b", "i2c_stop"},
        };

        for (String[] entry : knownFuncs) {
            Address addr = space.getAddress(Long.parseLong(entry[0].substring(2), 16));
            String name = entry[1];

            // Disassemble at this address
            DisassembleCommand cmd = new DisassembleCommand(addr, null, true);
            cmd.applyTo(currentProgram, monitor);

            // Create function
            Function func = fm.getFunctionAt(addr);
            if (func == null) {
                func = createFunction(addr, name);
            }
            if (func != null) {
                func.setName(name, SourceType.USER_DEFINED);
                println("Created function: " + name + " @ " + addr);
            }
        }

        // Also disassemble from every LJMP/LCALL target we can find
        // by scanning the binary for LJMP (0x02) and LCALL (0x12) opcodes
        // and disassembling at their targets
        Listing listing = currentProgram.getListing();
        byte[] rom = new byte[(int)currentProgram.getMemory().getSize()];
        currentProgram.getMemory().getBytes(space.getAddress(0), rom);

        int discovered = 0;
        for (int i = 0; i < rom.length - 2; i++) {
            int opcode = rom[i] & 0xFF;
            if (opcode == 0x02 || opcode == 0x12) {
                int target = ((rom[i+1] & 0xFF) << 8) | (rom[i+2] & 0xFF);
                if (target > 0 && target < rom.length) {
                    Address targetAddr = space.getAddress(target);
                    if (listing.getInstructionAt(targetAddr) == null) {
                        DisassembleCommand cmd = new DisassembleCommand(targetAddr, null, true);
                        cmd.applyTo(currentProgram, monitor);
                        discovered++;
                    }
                    // Create function at LCALL targets
                    if (opcode == 0x12 && fm.getFunctionAt(targetAddr) == null) {
                        try {
                            createFunction(targetAddr, null);
                        } catch (Exception e) {
                            // ignore if function creation fails
                        }
                    }
                }
            }
        }
        println("Discovered " + discovered + " additional code blocks from LJMP/LCALL targets");
        println("Total functions: " + fm.getFunctionCount());
    }
}
