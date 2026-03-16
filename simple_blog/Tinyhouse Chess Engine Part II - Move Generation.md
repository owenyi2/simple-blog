---
date: 2026-03-03
title: "Tinyhouse Chess Engine Part II: Move Generation"
---
This note follows on from [[Tinyhouse Chess Engine Part I - Introduction]]. For this note, I will be referring to code from my Python notebook which can be found [here](https://github.com/owenyi2/tinyhouse/blob/main/tinyhouse/main.ipynb). I have also rewritten it to Rust to implement a GUI which you can try out [here](https://owenyi2.github.io/tinyhouse/).
# Setup/Convention

```python
class Square(IntEnum):
    a4 = 0
    b4 = 1
    c4 = 2
    d4 = 3
    a3 = 4
    b3 = 5
    c3 = 6
    d3 = 7
    a2 = 8
    b2 = 9
    c2 = 10
    d2 = 11
    a1 = 12
    b1 = 13
    c1 = 14
    d1 = 15

BitBoard = int # specifically a u16 
```

The ordering of the squares is because if we arrange the squares visually

```
  4  . . . .
  3  . . . .
  2  . . . .
  1  . . . .

     a b c d
```
We can scan through left to right top to bottom

```
 0  1  2  3
 4  5  6  7
 8  9 10 11
12 13 14 15

So 0b0000_0100_0000_0001 is a BitBoard with a4 and c2 set
           ^           ^
           c2          a4
```

# Attack Masks

Given a piece is in a particular square, we want to know which squares are accessible to it. E.g. a Wazir on a2 can move to the following squares

```
  4  0 0 0 0
  3  1 0 0 0
  2  W 1 0 0
  1  1 0 0 0

     a b c d
```

An *attack mask* maps a single *square* to a *bitboard*. We will have an *attack mask* for each of 
- King
- Wazir
- Ferz
- White Pawn (attacks upwards towards the 4th rank)
- Black Pawn (attacks downwards towards the 1st rank)

Because the domain has only 16 elements, once we implement the functions to generate the attack masks, we can pre-compute the results and store them in a table

```python
KING_ATTACKS = [0 for _ in range(16)]
WAZIR_ATTACKS = [0 for _ in range(16)]
FERZ_ATTACKS = [0 for _ in range(16)]
PAWN_ATTACKS = [[0 for _ in range(16)], [0 for _ in range(16)]]

for square in range(16):
    KING_ATTACKS[square] = mask_king_attacks(square) # functions defined in below subsections
    WAZIR_ATTACKS[square] = mask_wazir_attacks(square)
    FERZ_ATTACKS[square] = mask_ferz_attacks(square)
    PAWN_ATTACKS[0][square] = mask_pawn_attacks(0, square) # White
    PAWN_ATTACKS[1][square] = mask_pawn_attacks(1, square) # Black
```

Because the Ma can be blocked by other pieces, the attacks available to a single Ma depend not only on the square it is on, but also on the complete occupancy bitboard (white occupancy | black occupancy). To efficiently look up Ma moves, we will need to use another technique: [[Tinyhouse Chess Engine Part II - Move Generation#Magic Tables]].


## Wazir

A wazir moves orthogonally 1 square. Therefore, by bitshifting by 1, we can get horizontal moves and bitshifting by 4 gives us vertical moves. 

```python
def mask_wazir_attacks(square: int) -> int:
    attacks = 0
    bitboard = 0
    bitboard = set_bit(bitboard, square)

    if (bitboard >> 4): attacks |= (bitboard >> 4) # Goes up 
    if ((bitboard >> 1) & NOT_D_FILE): attacks |= (bitboard >> 1)
    if (bitboard << 4): attacks |= (bitboard << 4) % U16_MAX 
    if ((bitboard << 1) & NOT_A_FILE): attacks |= (bitboard << 1) % U16_MAX 
    
    return attacks
```

Recall how the squares are numbered. 

```
#  0  1  2  3
#  4  5  6  7
#  8  9 10 11
# 12 13 14 15
```
Therefore
- `>> 4` moves 1 square up e.g. 5->1
- `<< 4` moves 1 square down e.g. 5->9
- `>> 1` moves 1 square left e.g. 5->4
- `<< 1`  moves 1 square right e.g. 5->6

Now observe there is a problem if we are on square 8 (a2) and we apply `>> 1` trying to move left. We are on the left most edge of the board and so `>> 1` will bring us to square 7 (d3). When we run `mask_wazir_attacks(8)` we want 

```
  4  0 0 0 0
  3  1 0 0 0
  2  0 1 0 0
  1  1 0 0 0

     a b c d 
```

and not

```
  4  0 0 0 0
  3  1 0 0 1
  2  0 1 0 0
  1  1 0 0 0

     a b c d 
```

Therefore we only include the result of `bitboard >> 1` if it will not cause a set bit on the d file (i.e. `& NOT_D_FILE` is non-zero) and similarly we only include result of `bitboard << 1` if it will not cause a set bit on the a file (i.e. `& NOT_A_FILE` is non-zero). This is not a problem for vertical moves because if we move off the edge, the set bit will either go beyond 0 or beyond the capacity of u16 and disappear regardless.

## Ferz

Diagonal moves are similar except we bitshift by 5 or 3 i.e. combining a vertical and horizontal move.

```python
def mask_ferz_attacks(square: int) -> int:
    attacks = 0
    bitboard = 0
    bitboard = set_bit(bitboard, square)

    if ((bitboard >> 5) & NOT_D_FILE): attacks |= (bitboard >> 5)
    if ((bitboard >> 3) & NOT_A_FILE): attacks |= (bitboard >> 3)
    if ((bitboard << 5) & NOT_A_FILE): attacks |= (bitboard << 5) % U16_MAX 
    if ((bitboard << 3) & NOT_D_FILE): attacks |= (bitboard << 3) % U16_MAX 
    
    return attacks
```

## King

We can simply take the union of the Ferz (diagonal) and Wazir (orthogonal) attacks.
```python
mask_king_attacks = lambda sqr: mask_ferz_attacks(sqr) | mask_wazir_attacks(sqr)
```

## Pawn

This is similar to the Ferz except the White pawn attacks up towards the 4th rank while the Black pawn attacks down towards the 1st rank.

```python
def mask_pawn_attacks(side: int, square: int) -> int:
    attacks = 0
    bitboard = 0
    bitboard = set_bit(bitboard, square)

    if side == Side.White: # White
        if ((bitboard >> 3) & NOT_A_FILE): attacks |= (bitboard >> 3)
        if ((bitboard >> 5) & NOT_D_FILE): attacks |= (bitboard >> 5)
    else:
        if ((bitboard << 3) & NOT_D_FILE): attacks |= (bitboard << 3)
        if ((bitboard << 5) & NOT_A_FILE): attacks |= (bitboard << 5)
    return attacks

```
# Ma moves

We require a function that computes the available moves for a Ma given 
1. The square it is on (16 possible values)
2. The bitboard showing which squares are occupied by other pieces ($2^{16}$ possible values)

This can be done slowly with this function which has a bunch of loops and checks to see if there are blockers in the way. 

```python
def generate_ma_attacks_on_the_fly(square: int, block_mask: int):
    attacks = 0
    
    tr = square // 4
    tf = square % 4

    deltas = {
        (0, 1): [(1, 2), (-1, 2)],
        (1, 0): [(2, 1), (2, -1)],
        (0, -1): [(1, -2), (-1, -2)],
        (-1, 0): [(-2, -1), (-2, 1)]
    }
    for (block_dr, block_df), attack_list in deltas.items():
        block_r = tr + block_dr
        block_f = tf + block_df
        block_square = 4 * block_r + block_f 

        if 0 <= block_square and block_square < 16 and (1 << (block_square) & block_mask):
            continue
        for dr, df in attack_list:
            r = tr + dr
            f = tf + df
            if 0 <= r and r < 4 and 0 <= f and f < 4:
                attacks |= 1 << (4 * r + f)
    return attacks
```

As it stands, since there are $2^{16}$ possible occupancy bitboards, we can't jump straight to pre-computing. However given the square that the Ma is on, we don't really care about the occupancy status of every square on the board, only the occupancy status of the 4 orthogonally adjacent squares to the Ma, since only those squares could restrict the movement of the Ma. In practice, due to how small the board is, the Ma's moves are already rather constrained and so 2 squares are enough to completely block the Ma. So only the occupancy status of 2 particular orthogonally adjacent squares are relevant. 

Consider the following blockers, and Ma location. Then the only squares that can block the b3 Ma's movement are c3 and b2. By BitAnd-ing the occupancy bitboard with the Wazir attack mask we can greatly constrain the size of the input domain. There are only $2^2$ relevant occupancy configurations to consider. Either none, c3, b2 or both are occupied. We can call this the relevant blockers bitboard.

```
Blockers
  4  . x . .
  3  . . x .
  2  . . . .
  1  . x x x

     a b c d 

Ma
  4  . . . .
  3  . M . .
  2  . . . .
  1  . . . .

     a b c d 

Relevant Blockers
  4  . x . .
  3  . . x .
  2  . . . .
  1  . . . .

     a b c d 
     
Attack Mask
  4  . . . .
  3  . . . .
  2  x . x .
  1  . . . .

     a b c d 
```

Since there are 16 possible squares the Ma can be on and effectively only 4 possible blocking patterns, a table of size $16 \times 4 = 64$ can represent the function for all possible inputs. The challenge now is to create a perfect hash to map (Square, Relevant Blockers bitboard) to Attack Mask. 

Our function for generating Ma moves will look like

```python
def generate_ma_attacks(square: Square, block_mask: int) -> int:
    block_mask &= WAZIR_ATTACKS[square] 
    block_mask *= MAGICS[square]
    magic_index = block_mask >> (16 - 2) # high two bits

    return MA_ATTACKS[square][magic_index]
```

The first step is to intersect the occupancy bitboard to produce the relevant blocker bitboard. We hash this into an index into our magic table `MA_ATTACKS` by multiplying the relevant blocker bitboard with the appropriate magic number from `MAGICS` and extracting the most significant two bits. Each square will have its own magic number to map $2^2$ possible relevant blocker bitboards into an index $\{0, 1, 2, 3\}$ where we can find the correct attack mask.

For each square, we generate an appropriate magic number by
1. Generating all possible blocking patterns
	- In general, a Ma can have at most 4 adjacent orthogonal squares and each square can either be occupied or not leaving at most $2^4$ possible patterns
	- Of these 4 adjacent squares, only 2 will actually be relevant to the Ma. That is while there could be $2^4$ unique possible relevant blocking patterns per square, we will only get $2^2$ unique attack patterns per square.
	- This is done by using the carry-rippler trick
		```python
		blockers = mask_wazir_attacks(square)
		blocking_patterns = []
		while True: 
			subset = (subset - blockers) & blockers # Iterates through all subsets of the set of set-bits in `blockers`
			blocking_patterns.append(subset)		
			if subset == 0:
				break
		```
2. For each blocking pattern, compute on the fly (slow) the correct attack mask
3. Spam random magic numbers until one works. To see if a number works,
	1. We create an empty table `used_attacks` of size 4
	2. Loop through each `pattern` from all possible relevant blocking patterns (at most 16 possible)
	- For a `pattern`, when we compute the hash `magic_index = (pattern * magic) >> (16 - 2)`, check that it either indexes into an empty space in `used_attacks` (in which case we populate that space with the correct attack mask from step 2) or that if the space is populated already, it still coincides with the attack mask required for this `pattern` also (i.e. constructive collision). 

```python
def generate_magic():
    return random.randint(0, 2**15-1) & random.randint(0, 2**15-1) & random.randint(0, 2**15-1) & random.randint(0, 2**15-1)

def find_magic_number(square: Square) -> Optional[int]:
    blocking_patterns = []
    subset = 0
    blockers = mask_wazir_attacks(square)
    # print_bitboard(blockers)
    while True:
        subset = (subset - blockers) & blockers
        blocking_patterns.append(subset)

        if subset == 0:
            break

    relevant_bits = 2

    attacks = []
    for pattern in blocking_patterns:
        attacks.append(generate_ma_attacks_on_the_fly(square, pattern))

    while True:
        # print("NEW")
        magic = generate_magic()
        used_attacks = [0 for _ in range(4)] # there are at most 4 attack squares for a Ma. Only 2 blockers are relevant. There are hence 2**2 unique attacks patterns per square
        fail = False
        for idx, pattern in enumerate(blocking_patterns):
            magic_index = (((pattern * magic) % U16_MAX) >> (16 - relevant_bits))  
            if used_attacks[magic_index] == 0:
                used_attacks[magic_index] = attacks[idx]
            elif used_attacks[magic_index] == attacks[idx]: # constructive collision: blocker configs that map to the same attack pattern (i.e. non-injectively)
                pass
            else:
                fail = True
                break
        if not fail:
            return magic

MA_ATTACKS = [[0 for _ in range(4)] for _ in range(16)]
MAGICS = [] 
for rank in range(4):
    for file in range(4):
        square = 4 * rank + file
        magic = find_magic_number(square)
        print(Square(square), magic)
        MAGICS.append(magic)
        blockers = mask_wazir_attacks(square) 
        relevant_bits = 2
        subset = 0
        while True:
            subset = (subset - blockers) & blockers
            magic_index = (((subset * magic) % U16_MAX) >> (16 - relevant_bits))
            MA_ATTACKS[square][magic_index] = generate_ma_attacks_on_the_fly(square, subset)

            if subset == 0:
                break
```

# Generating Pseudolegal Moves

Recall we are representing the Game State like so 

```python
@dataclass
class GameState:
    bitboards: list[int] # White King, Wazir, Ma, Ferz, Pawn + Black King, Wazir, Ma, Ferz, Pawn 
    occupancies: list[int] # white black 
    former_pawns: int
    side: int
    inventory: list[dict[Piece, int]]
```


We will define a generator to yield all possible moves from a particular game state.

```python
def generate_moves(game_state: GameState) -> Iterator[Move]:
```


## Placement

We can compute the available squares as `~(game_state.occupancies[0] | game_state.occupancies[1])`. For each piece in `game_state.inventory` and available square yield "piece placed at square". For pawns, we need to skip when the square is on 1st or 4th rank since that is an illegal move.

## Regular Piece Moves

For each piece, we extract the bitboard showing where all pieces of that type are. In the previous post we saw how `get_ls1b_index` allows us to iterate through the set bits of a bitboard efficiently. For each square set in that bitboard, we can look up the relevant attack mask from our precomputed table. We then intersect out squares occupied by our side since you cannot capture your own pieces. For the King, we also need to intersect out squares reachable by the enemy since we do not want to walk into check.

To compute the squares reachable by the enemy, it involves very similar logic to generating moves. We iterate through each piece of the enemy for each square occupied by a piece union together the attack mask of that piece at that square. 

```python
bitboard = game_state.bitboards[Piece.K]
# generate King Moves
if ((piece == Piece.K) if (side == 0) else (piece == Piece.k)):
	while bitboard:
		source_square = get_ls1b_index(bitboard)

		attacks = KING_ATTACKS[source_square] & ~occupancies[side] & ~enemy_attack_mask(game_state, game_state.side)
		while attacks:
			target_square = get_ls1b_index(attacks)

			# Quiet Move
			if not get_bit(occupancies[1 - side], target_square):
				yield Move(
					source = source_square, 
					target = target_square, 
					piece = piece, 
					promoted_piece = None, 
					capture = False, 
					placement = False
					)
			# Capture 
			else:
				yield Move(
					source = source_square, 
					target = target_square, 
					piece = piece, 
					promoted_piece = None, 
					capture = True, 
					placement = False)
			attacks = pop_bit(attacks, target_square)
		bitboard = pop_bit(bitboard, source_square)
```

For the Pawn it is very similar, however since Pawns move differently to how they attack, we also need to account for quiet moves by seeing if the square either forward (white) or backward (black) is accessible. For the other pieces, inaccessible squares are due to pieces on their one's own side but for pawns, inaccessible squares are due to pieces on both sides. 

For the initial state, we get the following moves. 
```
  4  f m w k
  3  . . . p
  2  P . . .
  1  K W M F

     a b c d

0 to play
  M: 1
[Move(source=None, target=4, piece=<Piece.M: 2>, promoted_piece=None, capture=False, placement=True),
 Move(source=None, target=5, piece=<Piece.M: 2>, promoted_piece=None, capture=False, placement=True),
 Move(source=None, target=6, piece=<Piece.M: 2>, promoted_piece=None, capture=False, placement=True),
 Move(source=None, target=9, piece=<Piece.M: 2>, promoted_piece=None, capture=False, placement=True),
 Move(source=None, target=10, piece=<Piece.M: 2>, promoted_piece=None, capture=False, placement=True),
 Move(source=None, target=11, piece=<Piece.M: 2>, promoted_piece=None, capture=False, placement=True),
 Move(source=12, target=9, piece=0, promoted_piece=None, capture=False, placement=False),
 Move(source=13, target=9, piece=1, promoted_piece=None, capture=False, placement=False),
 Move(source=14, target=5, piece=2, promoted_piece=None, capture=False, placement=False),
 Move(source=14, target=7, piece=2, promoted_piece=None, capture=True, placement=False),
 Move(source=15, target=10, piece=3, promoted_piece=None, capture=False, placement=False),
 Move(source=8, target=4, piece=4, promoted_piece=None, capture=False, placement=False)]
```

# Making Moves

We will require a function `def make_move(move: Move, game_state: GameState) -> GameState:` that applies a Move to a GameState to produce a new GameState.

Making moves is a straightforward but tedious process of popping and setting bits in the right places 
- For example a quiet move of a White Pawn involves
	- Popping the bit at the source square for the Pawn piece bitboard
	- Popping the bit at the source square for the White occupancy bitboard
	- Setting the bit at the target square for the Pawn piece bitboard
	- Setting the bit at the target square for the White occupancy bitboard
- A capture would require in addition
	- Popping the bit at the target square for every piece bitboard of the enemy (we don't know what piece was captured)
	- Popping the bit at the target square for the enemy occupancy bitboard

It is also important when a piece promotes, we set the former pawns bitboard and when said promoted piece moves, we also move it in the former pawns bitboard. This is because when you capture a piece that previously was a pawn, you only gain a pawn in your inventory and not the piece. 

```python
def make_move(move: Move, game_state: GameState) -> GameState:
    new_state = deepcopy(game_state)

    if move.placement:
        assert new_state.inventory[new_state.side][move.piece] > 0
        new_state.inventory[new_state.side][move.piece] -= 1
        new_state.bitboards[move.piece] = set_bit(new_state.bitboards[move.piece], move.target) # place piece
        new_state.occupancies[new_state.side] = set_bit(new_state.occupancies[new_state.side], move.target) # set occupancy on target
    else:
        if move.capture:
            for piece in range(10):
                if (new_state.bitboards[piece] & (1 << move.target)):
                    assert not ((piece == Piece.K) or (piece == Piece.k))
                    break
            else:
                assert False, "Unreachable"

            if get_bit(new_state.former_pawns, move.target):
                # captured a former pawn
                new_state.inventory[new_state.side][Piece.P if new_state.side == 0 else Piece.p] += 1
                new_state.former_pawns = pop_bit(new_state.former_pawns, move.target)
            else:
                new_state.inventory[new_state.side][(piece + 5) % 10] += 1

            new_state.bitboards[piece] = pop_bit(new_state.bitboards[piece], move.target) # additionally remove enemy piece
            new_state.occupancies[1-new_state.side] = pop_bit(new_state.occupancies[1-new_state.side], move.target) # additionally remove enemy occupancy from target
        
        # Handle Promotions
        if move.promoted_piece is not None:
            new_state.bitboards[move.piece] = pop_bit(new_state.bitboards[move.piece], move.source)
            new_state.bitboards[move.promoted_piece] = set_bit(new_state.bitboards[move.promoted_piece], move.target)
            new_state.former_pawns = set_bit(new_state.former_pawns, move.target)
        else:
            new_state.bitboards[move.piece] = set_bit(pop_bit(new_state.bitboards[move.piece], move.source), move.target) # move piece

        new_state.occupancies[new_state.side] = pop_bit(new_state.occupancies[new_state.side], move.source) # remove occupancy from source
        new_state.occupancies[new_state.side] = set_bit(new_state.occupancies[new_state.side], move.target) # set occupancy on target 

        # Move former pawn 
        if get_bit(new_state.former_pawns, move.source):
            new_state.former_pawns = set_bit(pop_bit(new_state.former_pawns, move.source), move.target) # move piece

    new_state.side = 1 - new_state.side
    return new_state
```


# Checks and Legal Moves

Currently our move generation doesn't care about checks. It will happily generate moves for all pieces even if the King is currently in check. In chess programming, there are two approaches
1. Generating Legal moves from the outset
2. Generating Pseudolegal moves, playing them to detect if they are illegal and then pruning if so

The second approach is simpler but we are wasting work generating illegal moves. It is fairly complex to purely generate Legal moves. Suppose the King is in check. Filtering to only King moves is insufficient because other pieces may block or capture the threat. Even in cases where the King is not in check, certain piece moves are illegal because they are pinned. 

Consider the situation when it is White (represented in capital letters) to play

```
  4  . . . k
  3  . m . .
  2  . W . .
  1  K . . .

     a b c d
     
```
Wazir to c2 would actually be an illegal move because it unblocks the enemy Ma leaving the White King in check after white's turn.

In contrast, playing the moves and computing check is simple. Check is when the union of the enemies' attack masks intersects with our King's bitboard.

```python
def detect_check(game_state: GameState, side: int):
    attack_mask = enemy_attack_mask(game_state, side)
    return bool(attack_mask & game_state.bitboards[Piece.K if side == 0 else Piece.k]) 

def generate_legal_moves(game_state):
    for move in generate_moves(game_state):
        if detect_check(make_move(move, game_state), game_state.side):
            continue
        yield move
```

# Perft

Chess Programming Wiki: https://www.chessprogramming.org/Perft

We can run `generate_legal_moves`, apply those moves and to those new positions continue recursively to see how many moves are possible at various depths. 

With my Python implementation it can reach a depth of 6-ply before it starts to get really slow.

```python
def perft(game_state: GameState, depth: int):
    if depth == 0:
        return 1
    count = 0
    for move in generate_legal_moves(game_state):
        count += perft(make_move(move, game_state), depth - 1)
    return count

for i in range(7):
    print(i, perft(default_game_state(), i))
```

```
0 1
1 6
2 33
3 246
4 1939
5 17231
6 153180
```

