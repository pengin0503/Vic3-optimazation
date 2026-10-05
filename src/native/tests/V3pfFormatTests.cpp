#include "Test.h"
#include "../common/V3pfFormat.h"
#include "../common/TraceWriter.h"
#include <fstream>
#include <iterator>
using namespace vic3;
static std::vector<std::byte> Read(const char* p) {std::ifstream f(p,std::ios::binary);CHECK(f);std::vector<std::byte> b;char c;while(f.get(c))b.push_back(std::byte(static_cast<unsigned char>(c)));return b;}
int main(int argc,char** argv) {
    CHECK(argc==3);const auto golden=Read(argv[1]);
    const std::string metadata=R"({"build_ids":{"caligula_branch":"release/1.14.5","caligula_rev":"9f8281a37e85639359b3b0c2c5df0196e975ca4b","clausewitz_branch":"caligula/release/1.14.x","clausewitz_rev":"fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef"},"profiler_build_id":"synthetic-reference-v1","targets":[{"kind":"synthetic","name":"SyntheticFunction","ranges":[{"begin_rva":"0x1000","end_rva":"0x1100"}],"target_id":1},{"kind":"synthetic","name":"SyntheticWait","ranges":[{"begin_rva":"0x2000","end_rva":"0x2100"}],"target_id":2}]})";
    const uint8_t target_hash[]{0x37,0xbc,0xd9,0x93,0xee,0xac,0xed,0xb4,0x50,0x35,0x23,0xd2,0xf4,0x76,0x96,0xff,0x92,0x3a,0x47,0xd3,0x23,0x78,0x5b,0x04,0xb3,0x1e,0x56,0x35,0xa5,0x18,0x33,0xd1};
    auto result=EncodeHeader(metadata,1000,90,target_hash,0,0);
    const uint16_t expected_size=616;CHECK(result.size()==expected_size);
    Event a{100,7,1,1,1,11}; auto b=a;b.type=3;b.timestamp=105;b.sequence=2;b.range_begin=10;b.range_end=20;b.range_length=10;b.task_threads=16;b.decision=2;b.reason_flags=3;b.work_count=4;
    auto c=a;c.type=4;c.timestamp=110;c.sequence=3;c.target=2;c.correlation=12;c.wait_kind=2;c.object_token=0xabc;
    auto d=a;d.timestamp=102;d.thread=8;d.correlation=21;
    auto e=c;e.type=5;e.timestamp=115;e.sequence=4;
    auto f=d;f.type=2;f.timestamp=120;f.sequence=2;
    auto g=a;g.type=2;g.timestamp=130;g.sequence=5;
    auto h=a;h.type=6;h.timestamp=135;h.sequence=6;h.target=0;h.counter_id=1;
    for(auto event:{a,b,c,d,e,f,g,h}){auto record=EncodeEvent(event);result.insert(result.end(),record.bytes.begin(),record.bytes.begin()+record.size);}
    CHECK(result==golden);
    Event begin{100,7,1,1,1,42};Event end{130,7,2,1,2,42};
    CHECK(EncodeEvent(begin).size==32);CHECK(EncodeEvent(end).size==40);
    std::filesystem::remove(argv[2]);
    {TraceWriter writer;writer.Open(argv[2],RuntimeMetadata(7,false),1000,90,generated::kTargetTableSha256);CHECK(writer.Write(EncodeEvent(begin)));CHECK(writer.Write(EncodeEvent(end)));CHECK(writer.Finalize(0));}
    bool failed=false;try{EncodeHeader(std::string(65536,'x'),1000,90,target_hash,0,0);}catch(const std::invalid_argument&){failed=true;}CHECK(failed);
    std::cout << "Exact Python golden bytes matched\n";
}
