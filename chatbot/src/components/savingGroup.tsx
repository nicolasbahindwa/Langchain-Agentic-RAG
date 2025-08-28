import React, { useState } from 'react';
import { 
  Home, 
  Users, 
  Wallet, 
  Receipt, 
  TrendingUp, 
  User, 
  MessageCircle, 
  Settings,
  Plus,
  Bell,
  Trophy,
  Target,
  Calendar,
  DollarSign,
  ArrowRight,
  Star,
  Shield,
  Award,
  Zap,
  ChevronRight,
  ArrowLeft,
  Check,
  AlertCircle,
  Heart,
  BookOpen,
  Eye,
  EyeOff,
  FileText,
  Vote,
  Clock,
  UserPlus,
  X,
  CheckCircle,
  XCircle
} from 'lucide-react';

// Main App Component with Navigation
function App() {
  const [currentPage, setCurrentPage] = useState('group-dashboard');
  const [userTier, setUserTier] = useState(3); // Tier 3 - Grower
  const [credibilityScore, setCredibilityScore] = useState(750);
  const [selectedGroupId, setSelectedGroupId] = useState(1);

  // Navigation items
  const navItems = [
    { id: 'group-dashboard', icon: Home, label: 'Group' },
    { id: 'my-groups', icon: Users, label: 'My Groups' },
    { id: 'wallet', icon: Wallet, label: 'Wallet' },
    { id: 'payments', icon: DollarSign, label: 'Payments' },
    { id: 'profile', icon: User, label: 'Profile' }
  ];

  const renderPage = () => {
    switch(currentPage) {
      case 'group-dashboard':
        return <GroupDashboard onNavigate={setCurrentPage} userTier={userTier} selectedGroupId={selectedGroupId} />;
      case 'my-groups':
        return <MyGroups onNavigate={setCurrentPage} userTier={userTier} onSelectGroup={setSelectedGroupId} />;
      case 'wallet':
        return <DigitalWallet onNavigate={setCurrentPage} />;
              case 'payments':
        return <PaymentConfirmation onNavigate={setCurrentPage} selectedGroupId={selectedGroupId} userTier={userTier} />;
      case 'profile':
        return <Profile onNavigate={setCurrentPage} userTier={userTier} credibilityScore={credibilityScore} />;
      case 'group-rules':
        return <GroupRules onNavigate={setCurrentPage} selectedGroupId={selectedGroupId} />;
      case 'group-members':
        return <GroupMembers onNavigate={setCurrentPage} selectedGroupId={selectedGroupId} />;
      case 'member-invitations':
        return <MemberInvitations onNavigate={setCurrentPage} selectedGroupId={selectedGroupId} />;
      case 'create-group':
        return <CreateGroup onNavigate={setCurrentPage} userTier={userTier} />;
      case 'invite-member':
        return <InviteMember onNavigate={setCurrentPage} selectedGroupId={selectedGroupId} userTier={userTier} />;
      case 'group-chat':
        return <GroupChat onNavigate={setCurrentPage} selectedGroupId={selectedGroupId} />;
      default:
        return <GroupDashboard onNavigate={setCurrentPage} userTier={userTier} selectedGroupId={selectedGroupId} />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            {currentPage !== 'group-dashboard' && (
              <button 
                onClick={() => setCurrentPage('group-dashboard')}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <ArrowLeft className="h-5 w-5 text-gray-600" />
              </button>
            )}
            <h1 className="text-xl font-bold text-gray-900">SaveTogether</h1>
          </div>
          <div className="flex items-center space-x-2">
            <button className="p-2 hover:bg-gray-100 rounded-lg relative">
              <Bell className="h-5 w-5 text-gray-600" />
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">2</span>
            </button>
            <button className="p-2 hover:bg-gray-100 rounded-lg">
              <Settings className="h-5 w-5 text-gray-600" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pb-20">
        {renderPage()}
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-2">
        <div className="flex justify-around">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentPage(item.id)}
                className={`flex flex-col items-center py-2 px-3 rounded-lg transition-colors ${
                  isActive 
                    ? 'text-blue-600 bg-blue-50' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Icon className="h-5 w-5 mb-1" />
                <span className="text-xs font-medium">{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

// Group Dashboard Component - Main view everyone in the group sees
function GroupDashboard({ onNavigate, userTier, selectedGroupId }) {
  const groupData = {
    id: 1,
    name: "Tech Entrepreneurs Circle",
    monthlyContribution: 200,
    totalMembers: 8,
    currentCycle: 5,
    totalCycles: 8,
    poolBalance: 1600,
    reservePool: 185,
    nextPayoutMember: "Member #3",
    payoutAmount: 1600,
    yourContributed: 1000,
    yourPosition: 3,
    cycleStartDate: "2024-01-15",
    tier: 3,
    cycleProgress: 62.5 // 5/8 cycles completed
  };

  const contributionStatus = {
    thisMonth: {
      paid: true,
      amount: 200,
      date: "2024-03-01",
      early: true
    },
    nextDue: "2024-04-01",
    deficit: 0, // Outstanding unpaid amounts - change to test deficit display
    advanceBalance: 150 // Overpayments that can cover future payments
  };

  return (
    <div className="p-4 space-y-6">
      {/* Group Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold">{groupData.name}</h2>
            <p className="text-blue-100">Cycle {groupData.currentCycle} of {groupData.totalCycles}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-blue-100">Tier {groupData.tier}</p>
            <p className="text-lg font-bold">${groupData.monthlyContribution}/month</p>
          </div>
        </div>

        {/* Cycle Progress Bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-blue-100">Cycle Progress</span>
            <span className="text-sm font-medium text-white">{groupData.cycleProgress}%</span>
          </div>
          <div className="w-full bg-white bg-opacity-20 rounded-full h-3">
            <div 
              className="bg-white bg-opacity-80 h-3 rounded-full transition-all duration-500" 
              style={{width: `${groupData.cycleProgress}%`}}
            ></div>
          </div>
          <p className="text-xs text-blue-100 mt-1">
            {groupData.totalCycles - groupData.currentCycle} cycles remaining
          </p>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white bg-opacity-20 rounded-xl p-3">
            <p className="text-sm mb-1">Pool Balance</p>
            <p className="text-xl font-bold">${groupData.poolBalance}</p>
          </div>
          <div className="bg-white bg-opacity-20 rounded-xl p-3">
            <p className="text-sm mb-1">Reserve Pool</p>
            <p className="text-xl font-bold">${groupData.reservePool}</p>
          </div>
        </div>
      </div>

      {/* Your Contribution Status */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-900">Your Contribution Status</h3>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${
            contributionStatus.thisMonth.paid 
              ? 'bg-green-100 text-green-800'
              : 'bg-orange-100 text-orange-800'
          }`}>
            {contributionStatus.thisMonth.paid ? 'Paid' : 'Pending'}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className="text-sm text-gray-600">Total Contributed</p>
            <p className="text-2xl font-bold text-blue-600">${groupData.yourContributed}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Queue Position</p>
            <p className="text-2xl font-bold text-purple-600">#{groupData.yourPosition}</p>
          </div>
        </div>

        {/* Deficit and Advance Balance Section */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="bg-gray-50 p-3 rounded-xl">
            <div className="flex items-center space-x-2 mb-1">
              <AlertCircle className={`h-4 w-4 ${contributionStatus.deficit > 0 ? 'text-red-600' : 'text-gray-400'}`} />
              <p className="text-sm text-gray-600">Outstanding Deficit</p>
            </div>
            <p className={`text-lg font-bold ${contributionStatus.deficit > 0 ? 'text-red-600' : 'text-gray-400'}`}>
              ${contributionStatus.deficit}
            </p>
            {contributionStatus.deficit > 0 && (
              <p className="text-xs text-red-500 mt-1">Needs immediate payment</p>
            )}
          </div>
          
          <div className="bg-green-50 p-3 rounded-xl">
            <div className="flex items-center space-x-2 mb-1">
              <Zap className={`h-4 w-4 ${contributionStatus.advanceBalance > 0 ? 'text-green-600' : 'text-gray-400'}`} />
              <p className="text-sm text-gray-600">Advance Balance</p>
            </div>
            <p className={`text-lg font-bold ${contributionStatus.advanceBalance > 0 ? 'text-green-600' : 'text-gray-400'}`}>
              ${contributionStatus.advanceBalance}
            </p>
            {contributionStatus.advanceBalance > 0 && (
              <p className="text-xs text-green-600 mt-1">
                Covers {Math.floor(contributionStatus.advanceBalance / groupData.monthlyContribution)} future payments
              </p>
            )}
          </div>
        </div>

        {/* Payment Action Buttons */}
        {contributionStatus.deficit > 0 ? (
          <div className="space-y-3">
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="flex items-center space-x-3">
                <AlertCircle className="h-5 w-5 text-red-600" />
                <div>
                  <h4 className="font-semibold text-red-900">Deficit Payment Required</h4>
                  <p className="text-sm text-red-700">
                    You have an outstanding deficit of ${contributionStatus.deficit} that needs to be paid
                  </p>
                </div>
              </div>
            </div>
            <button 
              onClick={() => onNavigate('payments')}
              className="w-full bg-red-600 text-white p-3 rounded-lg font-semibold hover:bg-red-700 transition-colors"
            >
              Pay Deficit + This Month - ${contributionStatus.deficit + groupData.monthlyContribution}
            </button>
          </div>
        ) : !contributionStatus.thisMonth.paid ? (
          <div className="space-y-3">
            <button 
              onClick={() => onNavigate('payments')}
              className="w-full bg-blue-600 text-white p-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors"
            >
              Make This Month's Payment - ${groupData.monthlyContribution}
            </button>
            <button 
              onClick={() => onNavigate('payments')}
              className="w-full bg-green-600 text-white p-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
            >
              Make Advance Payment (Extra Amount)
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="bg-green-50 p-3 rounded-lg">
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <span className="text-green-800 font-medium">
                  Payment completed on {contributionStatus.thisMonth.date}
                  {contributionStatus.thisMonth.early && " (Early payment +5 points)"}
                </span>
              </div>
            </div>
            <button 
              onClick={() => onNavigate('payments')}
              className="w-full bg-green-600 text-white p-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
            >
              Make Advance Payment for Future Months
            </button>
          </div>
        )}
      </div>

      {/* Next Payout Information */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Next Payout</h3>
        
        <div className="bg-gradient-to-r from-green-100 to-blue-100 p-4 rounded-xl">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Receiving Member</p>
              <p className="text-lg font-bold text-gray-900">{groupData.nextPayoutMember}</p>
              <p className="text-sm text-green-700">Payout: ${groupData.payoutAmount}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">Expected Date</p>
              <p className="font-bold text-gray-900">April 5, 2024</p>
            </div>
          </div>
        </div>
      </div>

      {/* Group Activity */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Recent Group Activity</h3>
        
        <div className="space-y-3">
          <div className="flex items-center space-x-3 p-3 bg-green-50 rounded-xl">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Member #5 paid $200 (Early payment)</p>
              <p className="text-xs text-gray-500">2 hours ago</p>
            </div>
            <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">+5 bonus</span>
          </div>

          <div className="flex items-center space-x-3 p-3 bg-blue-50 rounded-xl">
            <Zap className="h-5 w-5 text-blue-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Member #2 made advance payment $350</p>
              <p className="text-xs text-gray-500">5 hours ago</p>
            </div>
            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">+$150 advance</span>
          </div>

          <div className="flex items-center space-x-3 p-3 bg-orange-50 rounded-xl">
            <AlertCircle className="h-5 w-5 text-orange-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Member #7 paid deficit $250</p>
              <p className="text-xs text-gray-500">1 day ago</p>
            </div>
            <span className="text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded-full">Deficit cleared</span>
          </div>

          <div className="flex items-center space-x-3 p-3 bg-blue-50 rounded-xl">
            <DollarSign className="h-5 w-5 text-blue-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Pool reached $1,600 - Payout ready</p>
              <p className="text-xs text-gray-500">1 day ago</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-4">
        <button 
          onClick={() => onNavigate('create-group')}
          className="bg-gradient-to-r from-green-500 to-teal-500 p-4 rounded-xl text-white hover:from-green-600 hover:to-teal-600 transition-all"
        >
          <div className="flex flex-col items-center space-y-2">
            <Plus className="h-6 w-6" />
            <span className="font-semibold">Create Group</span>
          </div>
        </button>

        <button 
          onClick={() => onNavigate('my-groups')}
          className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="flex flex-col items-center space-y-2">
            <Users className="h-6 w-6 text-blue-600" />
            <span className="font-semibold text-gray-900">All Groups</span>
          </div>
        </button>
      </div>

      {/* Group Management */}
      <div className="grid grid-cols-2 gap-4">
        <button 
          onClick={() => onNavigate('group-members')}
          className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="flex flex-col items-center space-y-2">
            <Users className="h-6 w-6 text-blue-600" />
            <span className="font-semibold text-gray-900">View Members</span>
          </div>
        </button>

        <button 
          onClick={() => onNavigate('group-rules')}
          className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="flex flex-col items-center space-y-2">
            <FileText className="h-6 w-6 text-green-600" />
            <span className="font-semibold text-gray-900">Group Rules</span>
          </div>
        </button>

        <button 
          onClick={() => onNavigate('member-invitations')}
          className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="flex flex-col items-center space-y-2">
            <Vote className="h-6 w-6 text-purple-600" />
            <span className="font-semibold text-gray-900">Vote on Members</span>
          </div>
        </button>

        <button 
          onClick={() => onNavigate('group-chat')}
          className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
        >
          <div className="flex flex-col items-center space-y-2">
            <MessageCircle className="h-6 w-6 text-orange-600" />
            <span className="font-semibold text-gray-900">Group Chat</span>
          </div>
        </button>
      </div>
    </div>
  );
}

// Payment Confirmation Component
function PaymentConfirmation({ onNavigate, selectedGroupId, userTier }) {
  const [paymentConfirmed, setPaymentConfirmed] = useState(false);
  const [paymentType, setPaymentType] = useState('regular'); // 'regular', 'deficit', 'advance'
  const [advanceAmount, setAdvanceAmount] = useState('');
  
  const monthlyAmount = 200;
  const deficitAmount = 0; // This should be passed from the dashboard or retrieved from group data
  const walletBalance = 2847.50;
  
  const getPaymentAmount = () => {
    switch(paymentType) {
      case 'deficit':
        return monthlyAmount + deficitAmount;
      case 'advance':
        return monthlyAmount + (parseInt(advanceAmount) || 0);
      default:
        return monthlyAmount;
    }
  };

  const handleConfirmPayment = () => {
    setPaymentConfirmed(true);
    // Here you would integrate with actual payment processing
    setTimeout(() => {
      onNavigate('group-dashboard');
    }, 2000);
  };

  if (paymentConfirmed) {
    return (
      <div className="p-4 space-y-6">
        <div className="bg-green-50 rounded-2xl p-8 text-center">
          <CheckCircle className="h-16 w-16 text-green-600 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-green-900 mb-2">Payment Successful!</h2>
          <p className="text-green-700">Your contribution of ${getPaymentAmount()} has been processed</p>
          <div className="mt-4 space-y-2">
            <p className="text-sm text-green-600">+15 credibility points earned</p>
            {paymentType === 'advance' && (
              <p className="text-sm text-green-600">
                +${parseInt(advanceAmount) || 0} added to advance balance
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-6">
      {/* Payment Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">Confirm Payment</h2>
        <p className="text-blue-100">Tech Entrepreneurs Circle</p>
      </div>

      {/* Payment Type Selection */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Payment Type</h3>
        
        <div className="space-y-3">
          <label className="flex items-center space-x-3 p-3 border rounded-xl cursor-pointer hover:bg-gray-50">
            <input 
              type="radio" 
              name="paymentType" 
              value="regular"
              checked={paymentType === 'regular'}
              onChange={(e) => setPaymentType(e.target.value)}
              className="text-blue-600"
            />
            <div className="flex-1">
              <p className="font-medium text-gray-900">Regular Monthly Payment</p>
              <p className="text-sm text-gray-600">${monthlyAmount} - Standard contribution</p>
            </div>
          </label>

          {deficitAmount > 0 && (
            <label className="flex items-center space-x-3 p-3 border border-red-200 bg-red-50 rounded-xl cursor-pointer">
              <input 
                type="radio" 
                name="paymentType" 
                value="deficit"
                checked={paymentType === 'deficit'}
                onChange={(e) => setPaymentType(e.target.value)}
                className="text-red-600"
              />
              <div className="flex-1">
                <p className="font-medium text-red-900">Deficit + Monthly Payment</p>
                <p className="text-sm text-red-700">${monthlyAmount + deficitAmount} - Pay outstanding deficit</p>
              </div>
            </label>
          )}

          <label className="flex items-center space-x-3 p-3 border border-green-200 bg-green-50 rounded-xl cursor-pointer">
            <input 
              type="radio" 
              name="paymentType" 
              value="advance"
              checked={paymentType === 'advance'}
              onChange={(e) => setPaymentType(e.target.value)}
              className="text-green-600"
            />
            <div className="flex-1">
              <p className="font-medium text-green-900">Advance Payment</p>
              <p className="text-sm text-green-700">Monthly + extra amount for future coverage</p>
            </div>
          </label>

          {paymentType === 'advance' && (
            <div className="ml-8 mt-3">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Additional Advance Amount
              </label>
              <input 
                type="number" 
                value={advanceAmount}
                onChange={(e) => setAdvanceAmount(e.target.value)}
                placeholder="Enter additional amount"
                className="w-full p-3 border border-gray-300 rounded-lg"
              />
              <p className="text-xs text-gray-500 mt-1">
                This will be added to your advance balance for future payments
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Payment Details */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 space-y-4">
        <h3 className="text-lg font-bold text-gray-900">Payment Summary</h3>
        
        <div className="space-y-3">
          <div className="flex items-center justify-between py-2 border-b border-gray-200">
            <span className="text-gray-600">Monthly Contribution</span>
            <span className="font-bold text-gray-900">${monthlyAmount}</span>
          </div>

          {paymentType === 'deficit' && deficitAmount > 0 && (
            <div className="flex items-center justify-between py-2 border-b border-gray-200">
              <span className="text-red-600">Outstanding Deficit</span>
              <span className="font-bold text-red-600">${deficitAmount}</span>
            </div>
          )}

          {paymentType === 'advance' && advanceAmount && (
            <div className="flex items-center justify-between py-2 border-b border-gray-200">
              <span className="text-green-600">Advance Amount</span>
              <span className="font-bold text-green-600">${advanceAmount}</span>
            </div>
          )}

          <div className="flex items-center justify-between py-2 border-b border-gray-200">
            <span className="text-gray-600">Due Date</span>
            <span className="font-bold text-gray-900">April 1, 2024</span>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-gray-200">
            <span className="text-gray-600">Payment Method</span>
            <span className="font-bold text-gray-900">Wallet Balance</span>
          </div>

          <div className="flex items-center justify-between py-2">
            <span className="text-gray-600">Available Balance</span>
            <span className="font-bold text-green-600">${walletBalance}</span>
          </div>

          <div className="flex items-center justify-between py-3 bg-blue-50 rounded-lg px-4 font-bold text-lg">
            <span className="text-gray-900">Total Payment</span>
            <span className="text-blue-600">${getPaymentAmount()}</span>
          </div>
        </div>
      </div>

      {/* Payment Benefits */}
      {paymentType === 'advance' && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <div className="flex items-center space-x-3">
            <Zap className="h-5 w-5 text-green-600" />
            <div>
              <h4 className="font-semibold text-green-900">Advance Payment Benefits</h4>
              <p className="text-sm text-green-700">
                • Earn {userTier >= 3 ? '6%' : '3%'} annual interest on advance balance<br/>
                • Automatic coverage for future missed payments<br/>
                • Extra credibility points for responsible planning
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Early Payment Bonus */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex items-center space-x-3">
          <Star className="h-5 w-5 text-blue-600" />
          <div>
            <h4 className="font-semibold text-blue-900">Early Payment Bonus</h4>
            <p className="text-sm text-blue-700">Pay now and earn +5 extra credibility points!</p>
          </div>
        </div>
      </div>

      {/* Confirmation Button */}
      <div className="space-y-4">
        <button 
          onClick={handleConfirmPayment}
          disabled={walletBalance < getPaymentAmount()}
          className="w-full bg-blue-600 text-white p-4 rounded-xl font-bold hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Confirm Payment - ${getPaymentAmount()}
        </button>

        <button 
          onClick={() => onNavigate('wallet')}
          className="w-full bg-gray-100 text-gray-900 p-4 rounded-xl font-semibold hover:bg-gray-200 transition-colors"
        >
          Add Money to Wallet
        </button>
      </div>

      {/* Payment Info */}
      <div className="bg-blue-50 p-4 rounded-xl">
        <h4 className="font-semibold text-blue-900 mb-2">Payment Process</h4>
        <ul className="text-sm text-blue-700 space-y-1">
          <li>• Payment is deducted from your wallet immediately</li>
          <li>• You earn credibility points for timely payment</li>
          <li>• Early payments (5+ days) earn bonus points</li>
          <li>• Advance payments earn interest based on your tier</li>
          <li>• Payment cannot be reversed once confirmed</li>
        </ul>
      </div>
    </div>
  );
}

// Group Rules Component
function GroupRules({ onNavigate, selectedGroupId }) {
  const groupRules = {
    groupName: "Tech Entrepreneurs Circle",
    tier: 3,
    basicRules: [
      "Monthly contribution: $200 due by the 1st of each month",
      "8 members total, each gets 1 payout during the cycle",
      "Payout amount: $1,600 (8 × $200)",
      "Grace period: 7 days for late payments",
      "Reserve pool: 10% of monthly contributions"
    ],
    paymentRules: [
      "Late payments incur $10 penalty to reserve pool",
      "Missed payments completely: $25 penalty + strike",
      "Early payments (5+ days): +5 credibility points",
      "Overpayments earn 6% annual interest (Tier 3 benefit)"
    ],
    membershipRules: [
      "Must maintain Tier 3 or higher credibility",
      "Minimum 90% payment success rate required",
      "3-strike system: removal after 3rd strike",
      "New members require 80% group approval",
      "Anonymous member IDs allowed"
    ],
    payoutRules: [
      "Payout order determined by contribution ratio + random element",
      "Members with perfect payment record get priority",
      "Payouts processed within 24 hours of full pool",
      "Emergency fund access available for crises"
    ],
    governanceRules: [
      "Major decisions require 70% member approval",
      "Member removal requires group vote",
      "Rule changes need unanimous consent",
      "Emergency fund usage needs 60% approval"
    ]
  };

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-blue-600 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">Group Rules</h2>
        <p className="text-green-100">{groupRules.groupName} • Tier {groupRules.tier}</p>
      </div>

      {/* Basic Rules */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
          <FileText className="h-5 w-5 text-blue-600 mr-2" />
          Basic Group Rules
        </h3>
        <ul className="space-y-3">
          {groupRules.basicRules.map((rule, index) => (
            <li key={index} className="flex items-start space-x-3">
              <div className="bg-blue-100 text-blue-600 rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold mt-0.5">
                {index + 1}
              </div>
              <p className="text-gray-700">{rule}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* Payment Rules */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
          <DollarSign className="h-5 w-5 text-green-600 mr-2" />
          Payment Rules
        </h3>
        <ul className="space-y-3">
          {groupRules.paymentRules.map((rule, index) => (
            <li key={index} className="flex items-start space-x-3">
              <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
              <p className="text-gray-700">{rule}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* Membership Rules */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
          <Users className="h-5 w-5 text-purple-600 mr-2" />
          Membership Rules
        </h3>
        <ul className="space-y-3">
          {groupRules.membershipRules.map((rule, index) => (
            <li key={index} className="flex items-start space-x-3">
              <Shield className="h-5 w-5 text-purple-600 mt-0.5" />
              <p className="text-gray-700">{rule}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* Payout Rules */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
          <Trophy className="h-5 w-5 text-yellow-600 mr-2" />
          Payout Rules
        </h3>
        <ul className="space-y-3">
          {groupRules.payoutRules.map((rule, index) => (
            <li key={index} className="flex items-start space-x-3">
              <Star className="h-5 w-5 text-yellow-600 mt-0.5" />
              <p className="text-gray-700">{rule}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* Governance Rules */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
          <Vote className="h-5 w-5 text-red-600 mr-2" />
          Governance Rules
        </h3>
        <ul className="space-y-3">
          {groupRules.governanceRules.map((rule, index) => (
            <li key={index} className="flex items-start space-x-3">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <p className="text-gray-700">{rule}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// Group Members Component
function GroupMembers({ onNavigate, selectedGroupId }) {
  const [showRealNames, setShowRealNames] = useState(false);
  
  const members = [
    { 
      id: "TECH001", 
      realName: "Sarah Johnson (You)", 
      tier: 3, 
      paymentStatus: "paid", 
      contributionRatio: 1.0, 
      position: 3,
      isCurrentUser: true,
      strikes: 0
    },
    { 
      id: "TECH002", 
      realName: "Michael Chen", 
      tier: 4, 
      paymentStatus: "paid", 
      contributionRatio: 1.0, 
      position: 1,
      isCurrentUser: false,
      strikes: 0
    },
    { 
      id: "TECH003", 
      realName: "Anonymous", 
      tier: 3, 
      paymentStatus: "pending", 
      contributionRatio: 0.95, 
      position: 5,
      isCurrentUser: false,
      strikes: 1
    },
    { 
      id: "TECH004", 
      realName: "Emily Rodriguez", 
      tier: 3, 
      paymentStatus: "paid", 
      contributionRatio: 1.05, 
      position: 2,
      isCurrentUser: false,
      strikes: 0
    },
    { 
      id: "TECH005", 
      realName: "David Kim", 
      tier: 3, 
      paymentStatus: "paid", 
      contributionRatio: 0.98, 
      position: 4,
      isCurrentUser: false,
      strikes: 0
    },
    { 
      id: "TECH006", 
      realName: "Anonymous", 
      tier: 2, 
      paymentStatus: "paid", 
      contributionRatio: 1.0, 
      position: 6,
      isCurrentUser: false,
      strikes: 0
    },
    { 
      id: "TECH007", 
      realName: "Lisa Park", 
      tier: 3, 
      paymentStatus: "paid", 
      contributionRatio: 1.02, 
      position: 7,
      isCurrentUser: false,
      strikes: 0
    },
    { 
      id: "TECH008", 
      realName: "Anonymous", 
      tier: 3, 
      paymentStatus: "late", 
      contributionRatio: 0.88, 
      position: 8,
      isCurrentUser: false,
      strikes: 2
    }
  ];

  const getStatusColor = (status) => {
    switch(status) {
      case 'paid': return 'bg-green-100 text-green-800';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'late': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTierColor = (tier) => {
    const colors = {
      1: 'bg-gray-500',
      2: 'bg-blue-500',
      3: 'bg-green-500',
      4: 'bg-purple-500',
      5: 'bg-yellow-500'
    };
    return colors[tier];
  };

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-pink-600 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold mb-2">Group Members</h2>
            <p className="text-purple-100">8 active members</p>
          </div>
          <button 
            onClick={() => setShowRealNames(!showRealNames)}
            className="bg-white bg-opacity-20 p-3 rounded-full hover:bg-opacity-30 transition-all"
          >
            {showRealNames ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Invite New Member Button */}
      <button 
        onClick={() => onNavigate('invite-member')}
        className="w-full bg-green-600 text-white p-4 rounded-xl flex items-center justify-center space-x-2 hover:bg-green-700 transition-colors"
      >
        <UserPlus className="h-5 w-5" />
        <span className="font-semibold">Invite New Member</span>
      </button>

      {/* Privacy Toggle Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex items-center space-x-3">
          <Shield className="h-5 w-5 text-blue-600" />
          <div>
            <h4 className="font-semibold text-blue-900">Privacy Mode</h4>
            <p className="text-sm text-blue-700">
              {showRealNames ? "Showing member names (where available)" : "Showing anonymous member IDs only"}
            </p>
          </div>
        </div>
      </div>

      {/* Members List */}
      <div className="space-y-4">
        {members
          .sort((a, b) => a.position - b.position)
          .map((member) => (
          <div key={member.id} className={`bg-white rounded-2xl p-6 shadow-sm border ${
            member.isCurrentUser ? 'border-blue-200 bg-blue-50' : 'border-gray-200'
          }`}>
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <h3 className="font-bold text-gray-900">
                    {showRealNames ? member.realName : member.id}
                  </h3>
                  {member.isCurrentUser && (
                    <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                      You
                    </span>
                  )}
                </div>
                
                <div className="flex items-center space-x-4">
                  <div className={`${getTierColor(member.tier)} text-white px-2 py-1 rounded-full text-xs font-medium`}>
                    Tier {member.tier}
                  </div>
                  <div className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(member.paymentStatus)}`}>
                    {member.paymentStatus.charAt(0).toUpperCase() + member.paymentStatus.slice(1)}
                  </div>
                  {member.strikes > 0 && (
                    <div className="bg-red-100 text-red-800 px-2 py-1 rounded-full text-xs font-medium">
                      {member.strikes} Strike{member.strikes > 1 ? 's' : ''}
                    </div>
                  )}
                </div>
              </div>
              
              <div className="text-right">
                <p className="text-sm text-gray-600">Queue Position</p>
                <p className="text-xl font-bold text-purple-600">#{member.position}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600">Contribution Ratio</p>
                <p className={`font-bold ${
                  member.contributionRatio >= 1.0 ? 'text-green-600' : 
                  member.contributionRatio >= 0.95 ? 'text-yellow-600' : 'text-red-600'
                }`}>
                  {(member.contributionRatio * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Payment Status</p>
                <div className="flex items-center space-x-2">
                  {member.paymentStatus === 'paid' && <CheckCircle className="h-4 w-4 text-green-600" />}
                  {member.paymentStatus === 'pending' && <Clock className="h-4 w-4 text-yellow-600" />}
                  {member.paymentStatus === 'late' && <XCircle className="h-4 w-4 text-red-600" />}
                  <span className="text-sm font-medium capitalize">{member.paymentStatus}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Group Stats */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Group Statistics</h3>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-green-600">87.5%</p>
            <p className="text-sm text-gray-600">Payment Success Rate</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-blue-600">3.2</p>
            <p className="text-sm text-gray-600">Average Tier Level</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Member Invitations Component
function MemberInvitations({ onNavigate, selectedGroupId }) {
  const [votes, setVotes] = useState({});

  const pendingInvitations = [
    {
      id: "INV001",
      applicantId: "USER12345",
      tier: 3,
      creditScore: 680,
      paymentSuccessRate: 92,
      appliedDate: "2024-03-15",
      votesFor: 4,
      votesAgainst: 1,
      totalVotesNeeded: 6, // 80% of 8 members minus applicant
      status: "pending",
      timeRemaining: "2 days"
    },
    {
      id: "INV002",
      applicantId: "USER67890",
      tier: 2,
      creditScore: 720,
      paymentSuccessRate: 89,
      appliedDate: "2024-03-14",
      votesFor: 2,
      votesAgainst: 3,
      totalVotesNeeded: 6,
      status: "pending",
      timeRemaining: "1 day"
    }
  ];

  const handleVote = (invitationId, vote) => {
    setVotes({
      ...votes,
      [invitationId]: vote
    });
  };

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">Member Invitations</h2>
        <p className="text-indigo-100">Vote on new member applications</p>
      </div>

      {/* Voting Rules */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex items-center space-x-3 mb-3">
          <Vote className="h-5 w-5 text-blue-600" />
          <h4 className="font-semibold text-blue-900">Voting Requirements</h4>
        </div>
        <ul className="text-sm text-blue-700 space-y-1">
          <li>• 80% approval required for new members (6 out of 7 votes)</li>
          <li>• 72-hour voting period for each application</li>
          <li>• Must meet minimum tier and credit requirements</li>
          <li>• All current members can vote except applicant</li>
        </ul>
      </div>

      {/* Pending Applications */}
      {pendingInvitations.map((invitation) => (
        <div key={invitation.id} className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="font-bold text-gray-900 text-lg">Application #{invitation.id}</h3>
              <p className="text-gray-600">Applicant ID: {invitation.applicantId}</p>
              <p className="text-sm text-gray-500">Applied: {invitation.appliedDate}</p>
            </div>
            <div className="text-right">
              <div className="bg-orange-100 text-orange-800 px-3 py-1 rounded-full text-sm font-medium">
                {invitation.timeRemaining} left
              </div>
            </div>
          </div>

          {/* Applicant Stats */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="text-center">
              <p className="text-sm text-gray-600">Tier Level</p>
              <p className="text-lg font-bold text-blue-600">{invitation.tier}</p>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-600">Credit Score</p>
              <p className="text-lg font-bold text-green-600">{invitation.creditScore}</p>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-600">Success Rate</p>
              <p className="text-lg font-bold text-purple-600">{invitation.paymentSuccessRate}%</p>
            </div>
          </div>

          {/* Voting Progress */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Voting Progress</span>
              <span className="text-sm text-gray-600">
                {invitation.votesFor + invitation.votesAgainst} of {invitation.totalVotesNeeded + 1} votes
              </span>
            </div>
            
            <div className="grid grid-cols-2 gap-4 mb-3">
              <div className="text-center">
                <p className="text-xl font-bold text-green-600">{invitation.votesFor}</p>
                <p className="text-sm text-gray-600">For</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-bold text-red-600">{invitation.votesAgainst}</p>
                <p className="text-sm text-gray-600">Against</p>
              </div>
            </div>

            <div className="w-full bg-gray-200 rounded-full h-3">
              <div 
                className="bg-green-500 h-3 rounded-full transition-all duration-300" 
                style={{width: `${(invitation.votesFor / invitation.totalVotesNeeded) * 100}%`}}
              ></div>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Needs {invitation.totalVotesNeeded - invitation.votesFor} more votes to approve
            </p>
          </div>

          {/* Voting Buttons */}
          {!votes[invitation.id] ? (
            <div className="grid grid-cols-2 gap-4">
              <button 
                onClick={() => handleVote(invitation.id, 'approve')}
                className="bg-green-600 text-white p-3 rounded-xl font-semibold hover:bg-green-700 transition-colors flex items-center justify-center space-x-2"
              >
                <CheckCircle className="h-5 w-5" />
                <span>Approve</span>
              </button>
              <button 
                onClick={() => handleVote(invitation.id, 'reject')}
                className="bg-red-600 text-white p-3 rounded-xl font-semibold hover:bg-red-700 transition-colors flex items-center justify-center space-x-2"
              >
                <XCircle className="h-5 w-5" />
                <span>Reject</span>
              </button>
            </div>
          ) : (
            <div className={`p-3 rounded-xl text-center font-semibold ${
              votes[invitation.id] === 'approve' 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              You voted to {votes[invitation.id]} this application
            </div>
          )}
        </div>
      ))}

      {pendingInvitations.length === 0 && (
        <div className="bg-gray-50 rounded-2xl p-8 text-center">
          <UserPlus className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-600 mb-2">No Pending Applications</h3>
          <p className="text-gray-500">There are currently no new member applications to review.</p>
        </div>
      )}
    </div>
  );
}

// My Groups Component
function MyGroups({ onNavigate, userTier, onSelectGroup }) {
  const [activeTab, setActiveTab] = useState('active');

  const myGroups = [
    {
      id: 1,
      name: "Tech Entrepreneurs Circle",
      contribution: "$200",
      members: "8/8",
      status: "Active",
      tier: 3,
      yourPosition: 3,
      nextPayout: "You're next!",
      progress: 62
    },
    {
      id: 2,
      name: "Local Business Builders",
      contribution: "$150",
      members: "6/6",
      status: "Active",
      tier: 2,
      yourPosition: 5,
      nextPayout: "2 more cycles",
      progress: 75
    }
  ];

  const handleSelectGroup = (groupId) => {
    onSelectGroup(groupId);
    onNavigate('group-dashboard');
  };

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">My Groups</h2>
        <p className="text-blue-100">Manage your savings circles</p>
      </div>

      {/* Create Group Button */}
      <button 
        onClick={() => onNavigate('create-group')}
        className="w-full bg-green-600 text-white p-4 rounded-xl flex items-center justify-center space-x-2 hover:bg-green-700 transition-colors"
      >
        <Plus className="h-5 w-5" />
        <span className="font-semibold">Create New Group</span>
      </button>

      {/* Active Groups */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-gray-900">Active Groups</h3>
        
        {myGroups.map(group => (
          <div 
            key={group.id} 
            onClick={() => handleSelectGroup(group.id)}
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 cursor-pointer hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h4 className="font-bold text-gray-900 text-lg">{group.name}</h4>
                <p className="text-gray-600 text-sm">{group.contribution}/month • {group.members} members</p>
              </div>
              <div className="flex items-center space-x-2">
                <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                  group.tier <= 2 ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
                }`}>
                  Tier {group.tier}
                </div>
                <ChevronRight className="h-5 w-5 text-gray-400" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-sm text-gray-600">Your Position</p>
                <p className="font-bold text-purple-600">#{group.yourPosition}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Next Payout</p>
                <p className="font-bold text-green-600">{group.nextPayout}</p>
              </div>
            </div>

            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-500 h-2 rounded-full transition-all duration-300" 
                style={{width: `${group.progress}%`}}
              ></div>
            </div>
            <p className="text-xs text-gray-500 mt-1">Cycle progress: {group.progress}%</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// Create Group Component - Updated with tier restrictions
function CreateGroup({ onNavigate, userTier }) {
  const [formData, setFormData] = useState({
    name: '',
    contribution: '',
    maxMembers: 6,
    tier: userTier,
    duration: 12
  });

  const maxContributions = {
    1: 50,
    2: 150,
    3: 300,
    4: 750,
    5: 2000
  };

  const getTierInfo = (tier) => {
    const tierNames = {
      1: 'Beginner',
      2: 'Builder', 
      3: 'Grower',
      4: 'Elite',
      5: 'Master'
    };
    return tierNames[tier];
  };

  const handleSubmit = () => {
    // Here you would submit the group creation
    console.log('Creating group:', formData);
    onNavigate('my-groups');
  };

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-blue-600 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">Create New Group</h2>
        <p className="text-green-100">Start your own savings circle</p>
      </div>

      {/* Tier Restriction Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex items-center space-x-3">
          <Shield className="h-5 w-5 text-blue-600" />
          <div>
            <h4 className="font-semibold text-blue-900">Your Creation Privileges</h4>
            <p className="text-sm text-blue-700">
              As Tier {userTier} ({getTierInfo(userTier)}), you can create groups at Tier {userTier} or lower
            </p>
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Group Name</label>
          <input 
            type="text" 
            value={formData.name}
            onChange={(e) => setFormData({...formData, name: e.target.value})}
            className="w-full p-3 border border-gray-300 rounded-lg" 
            placeholder="Enter group name" 
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Group Tier</label>
          <select 
            value={formData.tier}
            onChange={(e) => setFormData({...formData, tier: parseInt(e.target.value)})}
            className="w-full p-3 border border-gray-300 rounded-lg"
          >
            {Array.from({length: userTier}, (_, i) => i + 1).map(tier => (
              <option key={tier} value={tier}>
                Tier {tier} - {getTierInfo(tier)} (Max: ${maxContributions[tier]})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Monthly Contribution (Max: ${maxContributions[formData.tier]})
          </label>
          <input 
            type="number" 
            value={formData.contribution}
            onChange={(e) => setFormData({...formData, contribution: e.target.value})}
            max={maxContributions[formData.tier]}
            className="w-full p-3 border border-gray-300 rounded-lg" 
            placeholder={`$50 - $${maxContributions[formData.tier]}`}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Maximum Members</label>
          <select 
            value={formData.maxMembers}
            onChange={(e) => setFormData({...formData, maxMembers: parseInt(e.target.value)})}
            className="w-full p-3 border border-gray-300 rounded-lg"
          >
            <option value={6}>6 members</option>
            <option value={8}>8 members</option>
            <option value={10}>10 members</option>
            <option value={12}>12 members</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Duration (months)</label>
          <select 
            value={formData.duration}
            onChange={(e) => setFormData({...formData, duration: parseInt(e.target.value)})}
            className="w-full p-3 border border-gray-300 rounded-lg"
          >
            <option value={6}>6 months</option>
            <option value={8}>8 months</option>
            <option value={10}>10 months</option>
            <option value={12}>12 months</option>
            <option value={15}>15 months</option>
            <option value={18}>18 months</option>
          </select>
        </div>

        {/* Group Preview */}
        {formData.contribution && (
          <div className="bg-gray-50 p-4 rounded-xl">
            <h4 className="font-semibold text-gray-900 mb-2">Group Preview</h4>
            <div className="text-sm text-gray-600 space-y-1">
              <p>• Monthly pool: ${formData.contribution * formData.maxMembers}</p>
              <p>• Payout amount: ${formData.contribution * formData.maxMembers}</p>
              <p>• Total cycle duration: {formData.maxMembers} payouts over {formData.duration} months</p>
              <p>• Reserve pool: 10% (${(formData.contribution * formData.maxMembers * 0.1).toFixed(0)}/month)</p>
            </div>
          </div>
        )}

        <button 
          onClick={handleSubmit}
          disabled={!formData.name || !formData.contribution}
          className="w-full bg-blue-600 text-white p-4 rounded-xl font-semibold hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Create Group
        </button>
      </div>
    </div>
  );
}

// Invite Member Component
function InviteMember({ onNavigate, selectedGroupId, userTier }) {
  const [inviteMethod, setInviteMethod] = useState('email');
  const [inviteData, setInviteData] = useState({
    email: '',
    phone: '',
    userId: '',
    message: ''
  });

  const groupData = {
    name: "Tech Entrepreneurs Circle",
    tier: 3,
    monthlyContribution: 200,
    currentMembers: 8,
    maxMembers: 10
  };

  const handleSendInvite = () => {
    // Here you would send the actual invitation
    console.log('Sending invite:', inviteData);
    onNavigate('group-members');
  };

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-blue-600 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">Invite New Member</h2>
        <p className="text-green-100">{groupData.name}</p>
        <p className="text-sm text-green-100 mt-1">
          {groupData.currentMembers}/{groupData.maxMembers} members • ${groupData.monthlyContribution}/month
        </p>
      </div>

      {/* Group Requirements */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex items-center space-x-3 mb-3">
          <Shield className="h-5 w-5 text-blue-600" />
          <h4 className="font-semibold text-blue-900">Member Requirements</h4>
        </div>
        <ul className="text-sm text-blue-700 space-y-1">
          <li>• Must have Tier {groupData.tier} or higher credibility level</li>
          <li>• Minimum 90% payment success rate required</li>
          <li>• Requires 80% group approval ({Math.ceil((groupData.currentMembers - 1) * 0.8)} votes)</li>
          <li>• Monthly contribution: ${groupData.monthlyContribution}</li>
        </ul>
      </div>

      {/* Invitation Method */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Invitation Method</h3>
        
        <div className="space-y-3 mb-4">
          <label className="flex items-center space-x-3 p-3 border rounded-xl cursor-pointer hover:bg-gray-50">
            <input 
              type="radio" 
              name="inviteMethod" 
              value="email"
              checked={inviteMethod === 'email'}
              onChange={(e) => setInviteMethod(e.target.value)}
              className="text-blue-600"
            />
            <div className="flex-1">
              <p className="font-medium text-gray-900">Email Invitation</p>
              <p className="text-sm text-gray-600">Send invitation link via email</p>
            </div>
          </label>

          <label className="flex items-center space-x-3 p-3 border rounded-xl cursor-pointer hover:bg-gray-50">
            <input 
              type="radio" 
              name="inviteMethod" 
              value="phone"
              checked={inviteMethod === 'phone'}
              onChange={(e) => setInviteMethod(e.target.value)}
              className="text-blue-600"
            />
            <div className="flex-1">
              <p className="font-medium text-gray-900">Phone Invitation</p>
              <p className="text-sm text-gray-600">Send invitation via SMS</p>
            </div>
          </label>

          <label className="flex items-center space-x-3 p-3 border rounded-xl cursor-pointer hover:bg-gray-50">
            <input 
              type="radio" 
              name="inviteMethod" 
              value="userId"
              checked={inviteMethod === 'userId'}
              onChange={(e) => setInviteMethod(e.target.value)}
              className="text-blue-600"
            />
            <div className="flex-1">
              <p className="font-medium text-gray-900">User ID</p>
              <p className="text-sm text-gray-600">Invite existing platform user by ID</p>
            </div>
          </label>
        </div>

        {/* Input Fields Based on Method */}
        <div className="space-y-4">
          {inviteMethod === 'email' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email Address</label>
              <input 
                type="email" 
                value={inviteData.email}
                onChange={(e) => setInviteData({...inviteData, email: e.target.value})}
                className="w-full p-3 border border-gray-300 rounded-lg" 
                placeholder="Enter email address"
              />
            </div>
          )}

          {inviteMethod === 'phone' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Phone Number</label>
              <input 
                type="tel" 
                value={inviteData.phone}
                onChange={(e) => setInviteData({...inviteData, phone: e.target.value})}
                className="w-full p-3 border border-gray-300 rounded-lg" 
                placeholder="Enter phone number"
              />
            </div>
          )}

          {inviteMethod === 'userId' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">User ID</label>
              <input 
                type="text" 
                value={inviteData.userId}
                onChange={(e) => setInviteData({...inviteData, userId: e.target.value})}
                className="w-full p-3 border border-gray-300 rounded-lg" 
                placeholder="Enter user ID (e.g., USER12345)"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Personal Message (Optional)</label>
            <textarea 
              value={inviteData.message}
              onChange={(e) => setInviteData({...inviteData, message: e.target.value})}
              className="w-full p-3 border border-gray-300 rounded-lg h-24" 
              placeholder="Add a personal message to your invitation..."
            />
          </div>
        </div>
      </div>

      {/* Invitation Preview */}
      <div className="bg-gray-50 rounded-2xl p-6">
        <h4 className="font-semibold text-gray-900 mb-3">Invitation Preview</h4>
        <div className="bg-white p-4 rounded-lg border text-sm">
          <p className="font-medium text-gray-900 mb-2">
            You've been invited to join "{groupData.name}"
          </p>
          <p className="text-gray-600 mb-3">
            • Monthly contribution: ${groupData.monthlyContribution}<br/>
            • Group tier: {groupData.tier}<br/>
            • Current members: {groupData.currentMembers}/{groupData.maxMembers}
          </p>
          {inviteData.message && (
            <div className="bg-blue-50 p-3 rounded-lg">
              <p className="text-sm text-blue-800 italic">"{inviteData.message}"</p>
            </div>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="space-y-4">
        <button 
          onClick={handleSendInvite}
          disabled={
            (inviteMethod === 'email' && !inviteData.email) ||
            (inviteMethod === 'phone' && !inviteData.phone) ||
            (inviteMethod === 'userId' && !inviteData.userId)
          }
          className="w-full bg-blue-600 text-white p-4 rounded-xl font-bold hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Send Invitation
        </button>

        <button 
          onClick={() => onNavigate('group-members')}
          className="w-full bg-gray-100 text-gray-900 p-4 rounded-xl font-semibold hover:bg-gray-200 transition-colors"
        >
          Cancel
        </button>
      </div>

      {/* Important Notes */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
        <div className="flex items-center space-x-3">
          <AlertCircle className="h-5 w-5 text-yellow-600" />
          <div>
            <h4 className="font-semibold text-yellow-900">Important Notes</h4>
            <ul className="text-sm text-yellow-700 mt-2 space-y-1">
              <li>• Invited members must meet tier requirements before joining</li>
              <li>• Group voting will begin once application is submitted</li>
              <li>• Invitation expires in 7 days if not accepted</li>
              <li>• You earn +25 credibility points for successful referrals</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

// Other components (DigitalWallet, Profile, GroupChat) remain similar but simplified for brevity
function DigitalWallet({ onNavigate }) {
  return (
    <div className="p-4 space-y-6">
      <div className="bg-gradient-to-r from-green-600 to-teal-600 rounded-2xl p-6 text-white">
        <h2 className="text-lg font-semibold mb-2">Wallet Balance</h2>
        <p className="text-3xl font-bold mb-4">$2,847.50</p>
        
        <div className="grid grid-cols-2 gap-4">
          <button className="bg-white bg-opacity-20 rounded-xl p-3 text-center hover:bg-opacity-30 transition-all">
            <Plus className="h-5 w-5 mx-auto mb-1" />
            <span className="text-sm font-medium">Add Money</span>
          </button>
          <button className="bg-white bg-opacity-20 rounded-xl p-3 text-center hover:bg-opacity-30 transition-all">
            <ArrowRight className="h-5 w-5 mx-auto mb-1" />
            <span className="text-sm font-medium">Send Money</span>
          </button>
        </div>
      </div>

      <div className="bg-blue-50 p-4 rounded-xl">
        <h4 className="font-semibold text-blue-900 mb-2">Auto-Payment Settings</h4>
        <p className="text-sm text-blue-700 mb-3">
          Enable automatic payments for your savings groups to never miss a contribution
        </p>
        <button className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium">
          Setup Auto-Pay
        </button>
      </div>
    </div>
  );
}

function Profile({ onNavigate, userTier, credibilityScore }) {
  return (
    <div className="p-4 space-y-6">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white">
        <div className="flex items-center space-x-4 mb-4">
          <div className="bg-white bg-opacity-20 p-4 rounded-full">
            <User className="h-8 w-8" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">Sarah Johnson</h2>
            <p className="text-blue-100">Tier {userTier} - Member since Jan 2024</p>
          </div>
        </div>
        
        <div className="bg-white bg-opacity-20 rounded-xl p-3">
          <p className="text-sm mb-1">Credibility Score</p>
          <p className="text-xl font-bold">{credibilityScore}</p>
        </div>
      </div>
    </div>
  );
}

function GroupChat({ onNavigate, selectedGroupId }) {
  return (
    <div className="p-4 space-y-6">
      <div className="bg-gradient-to-r from-blue-600 to-green-600 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">Group Chat</h2>
        <p className="text-blue-100">Tech Entrepreneurs Circle</p>
      </div>

      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <p className="text-gray-600 text-center">Group chat functionality would be implemented here</p>
      </div>
    </div>
  );
}

export default App;