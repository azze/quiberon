namespace Quiberon.Simulation;

/// <summary>CPython Random(integer seed) MT19937/double stream, solely for legacy map recipes.</summary>
internal sealed class PythonTerrainRandom
{
    private readonly uint[] state=new uint[624];
    private int index=624;
    public PythonTerrainRandom(long seed)
    {
        ulong magnitude=seed>=0?(ulong)seed:(ulong)(-(seed+1))+1;
        uint[] key=magnitude>uint.MaxValue?[(uint)magnitude,(uint)(magnitude>>32)]:[(uint)magnitude];
        unchecked {
            state[0]=19650218;
            for(int k=1;k<624;k++)state[k]=1812433253*(state[k-1]^(state[k-1]>>30))+(uint)k;
            int i=1,j=0;
            for(int k=624;k>0;k--){state[i]=(state[i]^((state[i-1]^(state[i-1]>>30))*1664525))+key[j]+(uint)j;i++;j++;if(i>=624){state[0]=state[623];i=1;}if(j>=key.Length)j=0;}
            for(int k=623;k>0;k--){state[i]=(state[i]^((state[i-1]^(state[i-1]>>30))*1566083941))-(uint)i;i++;if(i>=624){state[0]=state[623];i=1;}}
        }
        state[0]=0x80000000;
    }
    private uint Next()
    {
        if(index>=624){for(int i=0;i<624;i++){uint y=(state[i]&0x80000000)|(state[(i+1)%624]&0x7fffffff);state[i]=state[(i+397)%624]^(y>>1)^((y&1)==0?0:0x9908b0df);}index=0;}
        uint value=state[index++];value^=value>>11;value^=(value<<7)&0x9d2c5680;value^=(value<<15)&0xefc60000;value^=value>>18;return value;
    }
    public double NextDouble(){ulong a=Next()>>5,b=Next()>>6;return (a*67108864.0+b)/9007199254740992.0;}
}
