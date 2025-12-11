import pandapower as pp
import pandapower.networks as nw
try:
    from julia.api import Julia
    Julia(compiled_modules=False) # 必须加这个！
    print("✅ Julia init success")
except:
    print("❌ Julia init failed")

# 创建一个简单的 5 节点电网
net = nw.case5()

print("\nRunning OPF with PowerModels (Julia)...")
try:
    pp.runopp(net, algorithm='powermodels')
    if net.OPF_converged:
        print("🎉 SUCCESS! Julia solver worked!")
        print(f"Cost: {net.res_cost:.2f}")
    else:
        print("⚠️ Solver ran but didn't converge (unexpected for case5).")
except Exception as e:
    print(f"❌ FAILED: {e}")
    print("If this fails, your environment is still broken.")