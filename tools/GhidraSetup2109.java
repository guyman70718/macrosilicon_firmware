import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;

public class GhidraSetup2109 extends GhidraScript {
    @Override
    public void run() throws Exception {
        AddressFactory af = currentProgram.getAddressFactory();
        AddressSpace space = af.getDefaultAddressSpace();
        FunctionManager fm = currentProgram.getFunctionManager();
        Memory mem = currentProgram.getMemory();

        String[][] knownFuncs = {
            {"0x0000", "reset_vector"},
            {"0x0003", "ext0_isr"},
            {"0x000b", "timer0_isr"},
            {"0x0013", "ext1_isr"},
            {"0x001b", "timer1_isr"},
            {"0x0023", "serial_isr"},
            // MS2109-specific from ms-tools
            {"0x4648", "i2c_write_byte"},
            {"0x5F19", "eeprom_reload"},
            {"0x6A8C", "i2c_start"},
            {"0x6ABA", "i2c_stop"},
        };

        for (String[] entry : knownFuncs) {
            Address addr = space.getAddress(Long.parseLong(entry[0].substring(2), 16));
            DisassembleCommand cmd = new DisassembleCommand(addr, null, true);
            cmd.applyTo(currentProgram, monitor);
            Function func = fm.getFunctionAt(addr);
            if (func == null) func = createFunction(addr, entry[1]);
            if (func != null) func.setName(entry[1], SourceType.USER_DEFINED);
            println("Created: " + entry[1] + " @ " + addr);
        }

        // Scan for LJMP/LCALL targets
        byte[] rom = new byte[(int)mem.getSize()];
        mem.getBytes(space.getAddress(0), rom);
        int discovered = 0;
        Listing listing = currentProgram.getListing();
        for (int i = 0; i < rom.length - 2; i++) {
            int opcode = rom[i] & 0xFF;
            if (opcode == 0x02 || opcode == 0x12) {
                int target = ((rom[i+1] & 0xFF) << 8) | (rom[i+2] & 0xFF);
                if (target > 0 && target < rom.length) {
                    Address targetAddr = space.getAddress(target);
                    if (listing.getInstructionAt(targetAddr) == null) {
                        DisassembleCommand dcmd = new DisassembleCommand(targetAddr, null, true);
                        dcmd.applyTo(currentProgram, monitor);
                        discovered++;
                    }
                    if (opcode == 0x12 && fm.getFunctionAt(targetAddr) == null) {
                        try { createFunction(targetAddr, null); } catch (Exception e) {}
                    }
                }
            }
        }
        println("Discovered " + discovered + " code blocks, total functions: " + fm.getFunctionCount());
    }
}
