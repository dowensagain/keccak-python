import copy

class Keccakf1600_StateArray:
    A = []
    w = 64

    def __init__(self, input):
        self.__buildarray__(input)
    
    def __buildarray__(self, input):
        width = 2**self.w
        for i in range(5):                      # y: for each plane...
            self.A.append([])
            for j in range(5):                  # x: for each lane...
                t = input % width
                input //= width
                self.A[i].append(t)         # z: for each bit...
    
    def GetZ(self, x, y):
        return self.A[y][x]
    
    def SetZ(self, x, y, z):
        self.A[y][x] = z

    def GetBit(self, x, y, z):
        # x,y are flipped due to the way the array is structured
        return (self.A[y][x] >> z) & 1

    def SetBitTo(self, x, y, z, bit):
        if bit == 1:
            self.A[y][x] = self.A[y][x] | (1 << z - 1)
        else:
            mask = (2**64 - 1) - (2**z - 1) + (2**(z-1) - 1)
            self.A[y][x] = self.A[y][x] & mask


class Keccakf1600:

    # Permutation parameters
    b = 1600
    w = 64  # b/25
    l = 6   # log2(b/25)
    nr = 24
    ir = 0


    def __init__(self, input):
        self.StArr = Keccakf1600_StateArray(input)
    
    def Bits2Int(self, bits):
        out = 0
        for bit in bits:
            out = (out << 1) | bit
        return out

    def Theta(self):
        C = []
        D = []

        # Step 1
        for x in range(5):
            C.append([])
            for z in range(1,65):
                _C = self.StArr.GetBit(x,0,z) ^ self.StArr.GetBit(x,1,z) ^ self.StArr.GetBit(x,2,z) ^ self.StArr.GetBit(x,3,z) ^ self.StArr.GetBit(x,4,z)
                C[x].append(_C)

        # Step 2
        for x in range(5):
            D.append([])
            for z in range(self.w):
                _D = C[(x-1) % 5][z] ^ C[(x+1) % 5][(z-1) % self.w]
                D[x].append(_D)
        
        # Combine bits in D to integers
        D = [self.Bits2Int(bits) for bits in D]
        
        for y in range(5):
            for x in range(5):
                z_ = self.StArr.GetZ(x, y) ^ D[x]
                self.StArr.SetZ(x, y, z_)

    def Phi(self):
        # Step 1
        A_ = copy.deepcopy(self.StArr)
        A_.A = copy.deepcopy(self.StArr.A)

        # Step 2
        x = 1
        y = 0

        # Step 3
        for t in range(24):

            #Step 3a (little endian) (wrong?)
            # zA = [int(bit) for bit in format(self.StArr.A[y][x], '064b')]
            # zA_ = []
            # for z in range(self.w):
            #     p = (z-((t+1)*(t+2)//2)) % self.w
            #     zA_.append(zA[p])
            # A_.A[y][x] = self.Bits2Int(zA_)

            #Step 3a
            for z in range(1, self.w + 1):
                # Naive implementation that follows FIPS-202
                # A better approach would be to implement right rotate
                offset = (t+1)*(t+2)//2
                p = self.StArr.GetBit(x, y, (z-offset) % self.w)
                A_.SetBitTo(x, y, z, p)

            #Step 3b
            swap = x
            x = y
            y = ((2*swap) + (3*y)) % 5
            
        self.StArr = A_
        self.StArr.A = A_.A
    
    def PhiAlt(self):
        # Step 1
        A_ = copy.deepcopy(self.StArr)
        A_.A = copy.deepcopy(self.StArr.A)

        # Step 2
        x = 1
        y = 0

        # Step 3
        for t in range(24):

            offset = ((t+1)*(t+2)//2) % self.w
            A_.A[y][x] = ROR(self.StArr.A[y][x], 64, offset)

            #Step 3b
            swap = x
            x = y
            y = ((2*swap) + (3*y)) % 5
            
        self.StArr = A_
        self.StArr.A = A_.A

    def Pi(self):
        A_ = copy.deepcopy(self.StArr)
        A_.A = copy.deepcopy(self.StArr.A)

        for y in range(5):
            for x in range(5):
                for z in range(1,65):
                    z_ = self.StArr.GetBit((x + 3*y) % 5, x, z)
                    A_.SetBitTo(x, y, z, z_)

        self.StArr = A_
        self.StArr.A = A_.A

    def Chi(self):
        A_ = copy.deepcopy(self.StArr)
        A_.A = copy.deepcopy(self.StArr.A)

        for y in range(5):
            for x in range(5):
                for z in range(1,65):
                    z1 = self.StArr.GetBit(x, y, z)
                    z2 = self.StArr.GetBit((x+1) % 5, y, z) ^ 1
                    z3 = self.StArr.GetBit((x+2) % 5, y, z)
                    z_ = z1 ^ (z2 & z3)
                    A_.SetBitTo(x, y, z, z_)
        
        self.StArr = A_
        self.StArr.A = A_.A

    def rc(self, t):
        if t % 255 == 0: return 1
        R = 0b10000000                    
        for i in range(t % 255):                                      
            R8 = R & 1                         
            R0 = 0 ^ R8 #((R >> 9) & 1) ^ R8            #       123456789
            R4 = ((R >> 5) & 1) ^ R8                    #       012345678
            R5 = ((R >> 4) & 1) ^ R8                    # R = 0b010000000
            R6 = ((R >> 3) & 1) ^ R8                    #       x   xxx  

            R_ = (R0 << 3) | ((R >> 5) & 0b111)
            R_ = (R_ << 1) | R4
            R_ = (R_ << 1) | R5
            R_ = (R_ << 1) | R6
            R_ = (R_ << 2) | R & 0b11

            R |= R_
            R >>= 1

        return R >> 8

    def Ro(self):
        A_ = copy.deepcopy(self.StArr)
        A_.A = copy.deepcopy(self.StArr.A)
        RC = [0]*self.w
        for j in range(self.l):
            RC[2**j - 1] = self.rc(j + 7*self.ir)
        for z in range(1,self.w + 1):
            bit = A_.GetBit(0, 0, z)
            A_.SetBitTo(0, 0, z, bit ^ RC[z - 1])
        self.StArr = A_
        self.StArr.A = A_.A

    def __Round(self):
        self.Theta()
        self.Phi()
        self.Phi()
        self.Chi()
        self.Ro()

    def Run(self):
        for i in range(self.nr):
            self.__Round()


def ROR(num, bitlength, offset):
    for i in range(1, offset + 1):
        bit = num & 1
        mask = ((bit << bitlength - 1) & 2**(bitlength - 1))
        num = (num >> 1) | mask
    return num