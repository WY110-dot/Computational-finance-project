import unittest,sys,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.factors import calculate,forward_label,diagnose,groups_at_formation
from src.backtest import allocate,simulate,audit,metrics

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.dates=pd.bdate_range('2020-01-01',periods=80)
        arr=100*np.exp(np.arange(80)[:,None]*np.array([.001,.002,-.001])[None])
        self.close=pd.DataFrame(arr,index=self.dates,columns=['A','B','C'])
        self.p={k:self.close.copy() for k in ['open','close']};self.p['volume']=self.close*0+1000
        self.cfg=dict(start=str(self.dates[25].date()),end=str(self.dates[-1].date()),initial_cash=1000.,buy_fee=.001,sell_fee=.002,
            invest_fraction=.99,top_n=1,min_assets=2,annualization=252,daily_risk_free=0.,adv_window=20,participation=.001,max_stale_days=5,groups=3)
        self.f=calculate(self.close,dict(momentum=20,reversal=5,low_volatility=20))
    def test_factor_hand_calculation(self):
        self.assertAlmostEqual(self.f['momentum'].iloc[20,0],np.exp(.02)-1)
        self.assertAlmostEqual(self.f['reversal'].iloc[5,0],-(np.exp(.005)-1))
        self.assertTrue(self.f['low_volatility'].iloc[:20].isna().all().all())
    def test_next_open_label(self):
        y=forward_label(self.p['open'],5)
        self.assertAlmostEqual(y.iloc[10,1],self.p['open'].iloc[16,1]/self.p['open'].iloc[11,1]-1)
        self.assertTrue(y.iloc[-6:].isna().all().all())
    def test_cash_and_actual_fees(self):
        b,s,c,fee=allocate([200.,-50.],[np.inf,np.inf],100,.01,.02)
        self.assertAlmostEqual(s.sum(),50);self.assertAlmostEqual(b.sum(),149/1.01)
        self.assertAlmostEqual(c,0);self.assertAlmostEqual(fee,b.sum()*.01+1)
    def test_partial_fills(self):
        b,s,c,fee=allocate([500.,-100.],[50.,20.],200,.01,.02)
        np.testing.assert_allclose(b,[50,0]);np.testing.assert_allclose(s,[0,20]);self.assertAlmostEqual(fee,.9)
        self.assertAlmostEqual(c,169.1)
    def test_unfilled_order_no_fee(self):
        b,s,c,f=allocate([100.,-50.],[0.,0.],100,.01,.01)
        self.assertEqual(f,0);self.assertEqual(c,100)
    def test_constant_ic_is_nan_and_average_ties(self):
        constant=self.close*0+1;labels=forward_label(self.close,5)
        ic,g,s=diagnose({'constant':constant},labels,self.cfg)
        self.assertTrue(ic.ic.isna().all());self.assertTrue(ic.rank_ic.isna().all())
        v=pd.Series([1,1,2],index=['B','A','C']);self.assertEqual(list(v.rank(method='average')),[1.5,1.5,3.])
    def test_groups_do_not_depend_on_label(self):
        a=groups_at_formation(pd.Series([3,1,2],index=['A','B','C']),3,2)
        self.assertEqual(a.to_dict(),{'B':1,'C':2,'A':3})
    def test_initial_drawdown_included(self):
        d=pd.DataFrame(dict(daily_return=[-.1,0.],wealth=[900.,900.],cost=[100,0],turnover=[1,0],holdings=[1,1],max_weight=[1,1],requested=[1000,0],unfilled=[0,0]))
        self.assertAlmostEqual(metrics(d,self.cfg)['max_drawdown'],.1)
    def test_future_prefix_and_current_open_order(self):
        d,t,h=simulate(self.p,self.f['momentum'],self.cfg,frequency='daily')
        p={k:v.copy() for k,v in self.p.items()};p['close'].iloc[50:]*=2;p['open'].iloc[51:]*=3;p['volume'].iloc[50:]*=100
        f=calculate(p['close'],dict(momentum=20))['momentum'];dd,tt,hh=simulate(p,f,self.cfg,frequency='daily')
        np.testing.assert_allclose(d[d.date<self.dates[50]].wealth,dd[dd.date<self.dates[50]].wealth)
        np.testing.assert_allclose(t[t.date<=self.dates[50]].executed_dollars,tt[tt.date<=self.dates[50]].executed_dollars)
    def test_missing_open_freezes_and_audits(self):
        p={k:v.copy() for k,v in self.p.items()};p['open'].iloc[30]=np.nan
        d,t,h=simulate(p,self.f['momentum'],self.cfg,frequency='daily')
        self.assertEqual(d.loc[d.date==self.dates[30],'cost'].iloc[0],0)
        audit(d,t,h,self.cfg)
    def test_lagged_capacity_and_repeatability(self):
        d,t,h=simulate(self.p,self.f['momentum'],self.cfg,limited=True);audit(d,t,h,self.cfg)
        self.assertLess(d.buy.iloc[0],990)
        dd,tt,hh=simulate(self.p,self.f['momentum'],self.cfg,limited=True)
        pd.testing.assert_frame_equal(d,dd);pd.testing.assert_frame_equal(t,tt)
        p={k:v.copy() for k,v in self.p.items()};p['volume'].iloc[25]*=1e6
        d2,_,_=simulate(p,self.f['momentum'],self.cfg,limited=True)
        self.assertAlmostEqual(d.buy.iloc[0],d2.buy.iloc[0])
    def test_infinite_capacity_recovers_baseline(self):
        d,_,_=simulate(self.p,self.f['momentum'],self.cfg)
        dd,_,_=simulate(self.p,self.f['momentum'],{**self.cfg,'participation':1e12},limited=True)
        np.testing.assert_allclose(d.wealth,dd.wealth)
    def test_corrupted_ledger_rejected(self):
        d,t,h=simulate(self.p,self.f['momentum'],self.cfg);d.loc[0,'cost']+=1
        with self.assertRaises(AssertionError):audit(d,t,h,self.cfg)

if __name__=='__main__':unittest.main(verbosity=2)
